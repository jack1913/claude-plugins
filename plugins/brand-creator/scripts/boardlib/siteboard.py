"""The rows of the website references board (data-board="site-refs"): a round after G4 that shows the owner groups of real sites to learn from, before any page of the site is built.

The board is an ordinary round (rounds/rN/board.html, N 2 or more), from templates/site-refs-board.html. This file holds the rows that need more than the page: the gates of the work
(refs_gate_rows: site-refs:tier, site-refs:brief, site-refs:g4, site-refs:research, site-refs:cliches-file) and the reading of brief/BRIEF.md that decides whether the project has a
site at all (brief_lists_site). The sections and the group count are board_lint's own, with the other kinds of board. The rows of the page itself are here too: owner_rows (owner-sites:items: the sites the owner named) and
group_rows (group:<name>:name, :idea, :references, :layout and, one per reference, :shot:<k>). A site round (data-board="site") will add its rows here.

A screenshot on the board is checked against the captures. group_rows reads every research/site-refs/<name>/capture.json (written by `brand-creator capture --url`): a screenshot whose bytes are a
thumbnail or a view listed there, for the address the reference links to, passes; one that matches no capture is a warning, never a failure, and never silent (a screenshot the owner sent has no
capture, and the caption says so). Every capture.json is an input of the lint report, so a new capture makes the lint stale.

Whether the brief lists a site is read from the value after "Required surfaces:" in brief/BRIEF.md, against a list of English and Polish words (SITE_WORDS). A value wrapped in parentheses is the untouched
line of the template ("(site, app icon, ...)"), the owner's own words not yet written, and does not count. A brief in another language is not recognised: the owner adds the word "site" to the line.

The folder of boardlib is outside scripts/lib/, so a change here does not make every pack stale. Standard library only (plus _common, boardpage, motionboard, reflex and sitedata); no clock and no network. The only reads are the board's project files: the capture records and the layout file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from _common import Report, gate_recorded, read_state, rel, sha256_bytes
from boardpage import DATA_IMAGE, GENERIC_NAME, PLACEHOLDER, WORD_NAME, Node, sections, thumb_problems
import motionboard
import reflex
import sitedata

BRIEF_FILE = "brief/BRIEF.md"
CLICHES_FILE = "research/site-cliches.md"
MIN_CLICHES = 3                     # site-refs:cliches-file: items under "Avoid unless argued" that the file needs
TIERS = ("standard", "full")        # the site work is optional and runs in these tiers only
ANSWERS = ("online", "links-only", "none")   # the answers to the online-research question that count as asked (site_research: auto is not asked yet)
# What counts as "a site" on the Required surfaces line, in English and Polish: site(s), website(s), microsite(s), web page(s), landing page(s), www, strona and its forms, also typed without diacritics and the diminutive stronka (never "strong"), witryna and its forms.
SITE_WORDS = re.compile(r"\b(?:(?:web|micro)?sites?|web[\s-]?pages?|landing[\s-]?pages?|www|stron(?:a|y|e|ę|ą|ie|om|ami|ach|ka|ki|ke|kę|ką)?|witryn(?:a|y|e|ę|ą|ie|om|ami|ach)?)\b", re.I)
SURFACES_LINE = re.compile(r"^[ \t>*_-]*required[ \t]+surfaces[ \t]*\**[ \t]*:[ \t]*\**[ \t]*(.*?)[ \t\r]*$", re.I | re.M)   # "- Required surfaces: ...", also with the label in bold; spaces and tabs only, so an empty line never reads the next one


def brief_lists_site(project: Path) -> tuple[bool, str]:
    """(whether the brief lists a site, the detail that says why). Reads the first "Required surfaces:" line of brief/BRIEF.md, case-insensitively; a value wrapped in parentheses is the template line
    and does not count. The detail names the line, so the owner can see what was read."""
    brief = Path(project) / BRIEF_FILE
    if not brief.is_file():
        return False, f"{BRIEF_FILE} is missing, so the surfaces the brand needs are not known"
    m = SURFACES_LINE.search(brief.read_text(encoding="utf-8", errors="replace"))
    if m is None:
        return False, f'{BRIEF_FILE} has no "Required surfaces:" line'
    value = m.group(1).strip()
    if not value:
        return False, f"{BRIEF_FILE}: the Required surfaces line is empty"
    if value.startswith("(") and value.endswith(")"):
        return False, f"{BRIEF_FILE}: the Required surfaces line is still the template's ({value}): the owner has not named the surfaces"
    word = SITE_WORDS.search(value)
    if word is None:
        return False, f'{BRIEF_FILE}: "Required surfaces: {value}" names no site (a brief in a language other than English or Polish needs the word "site" on that line)'
    return True, f'{BRIEF_FILE}: "Required surfaces: {value}" lists a site ("{word.group(0)}")'


def refs_gate_rows(rep: Report, project: Path) -> None:
    """site-refs:tier (Standard or Full), site-refs:brief (the brief lists a site), site-refs:g4 (the system rules are approved), site-refs:research (the owner answered the online-research question)
    and site-refs:cliches-file (research/site-cliches.md has 3 or more items to avoid). The lint report lists the brief and the cliché file as inputs when they exist, so a change to either makes it stale."""
    for f in (Path(project) / BRIEF_FILE, Path(project) / CLICHES_FILE):
        if f.is_file():
            rep.inputs.append(f)
    state = read_state(project)

    tier = str(state.get("tier", "") or "").strip().lower()
    rep.add("site-refs:tier", "pass" if tier in TIERS else "fail", "the site work is Standard and Full",
            detail=f"tier: {tier}" if tier in TIERS else f"the site work is Standard and Full (this project's tier is {tier or 'missing'}): website references are not offered in the Quick tier")

    listed, why = brief_lists_site(project)
    rep.add("site-refs:brief", "pass" if listed else "fail", "the brief lists a site",
            detail=why if listed else f"the website references run only when {BRIEF_FILE} lists a site under Required surfaces, in the owner's words; ask the owner ({why})")

    g4 = gate_recorded(project, "G4")
    rep.add("site-refs:g4", "pass" if g4 else "fail", "website references come after the system rules (G4)",
            detail=f"G4: {g4}" if g4 else "website references come after the system rules (G4): record the owner's approval first (`brand-creator state --record G4 \"<decision>\"`)")

    answer = str(state.get("site_research", "") or "").strip().lower()
    rep.add("site-refs:research", "pass" if answer in ANSWERS else "fail", "the owner answered the online-research question",
            detail=f"site_research: {answer}" if answer in ANSWERS else
                   f"ask the owner the online-research question first and record it: state --set site_research=online|links-only|none (site_research is {answer or 'missing'})")

    items = reflex.cliche_items(project, rel=CLICHES_FILE)
    label = f"{CLICHES_FILE} lists {MIN_CLICHES} or more site clichés to avoid unless argued"
    if not (Path(project) / CLICHES_FILE).is_file():
        rep.add("site-refs:cliches-file", "fail", label, detail=f"{CLICHES_FILE} is missing: copy templates/site-cliches.md there and fill it from the sites opened for the references")
    elif len(items) < MIN_CLICHES:
        rep.add("site-refs:cliches-file", "fail", label,
                detail=f"{len(items)} item(s) under \"## Avoid unless argued\" in {CLICHES_FILE}, need at least {MIN_CLICHES} (a placeholder such as (...) does not count): they go into the reflex test of each hero variant")
    else:
        rep.add("site-refs:cliches-file", "pass", label, detail=f"{len(items)} items under \"## Avoid unless argued\"")


# ---------------------------------------------------------------- the groups, the references, the screenshots

CAPTURES = "research/site-refs/*/capture.json"   # the records `brand-creator capture --url` writes, one folder per site (research/site-refs/owner/ holds the owner's own screenshots: no record)
MIN_REFERENCES = 3                               # group:<name>:references: sites in a group
OWN_LAYOUT = re.compile(r"own:[a-z][a-z0-9-]{1,31}")   # a layout of the group's own: allowed with a warning, so the references never become a menu of templates
HTTP_LINK = re.compile(r"https?://\S+", re.I)
# "Group 2", "Cluster B", "Type II", "Set 3": a label, not a word. The shared GENERIC_NAME (boardpage) knows "Option", "Style", "Territory" and the like; a group is also labelled "group", "cluster", "layout" and the like.
GENERIC_GROUP = re.compile(r"^(?:groups?|clusters?|types?|sets?|categor(?:y|ies)|approach(?:es)?|patterns?|layouts?)(?:\d+|[\s#-]+(?:\d+|[^\W\d_]|[ivxlcdm]{2,8}))?$", re.I)
# The template writes "Take: " and "Avoid: " inside the fields, and " · shown for private research" after the caption's words: none of them is the author's.
FIELD_LABELS = {fid: re.compile(rf"^\s*{fid}\s*(?::|(?=\W*$))", re.I) for fid in ("take", "avoid")}   # "Take:" and anything after it; or "Take" alone, or "Take" and only dashes and dots
CAPTION_TAIL = re.compile(r"\s*[·•|-]?\s*shown for private research\s*\.?\s*$", re.I)
DEFAULT_PORTS = {"http": ":80", "https": ":443"}
SHOT_LABEL = "the screenshot is a capture of the site it shows"
CAPTURE_FIX = "capture it (brand-creator capture --url {href} --name <name>), or say in the caption that the owner sent the screenshot"


def shown(problems: list[str], limit: int = 6) -> str:
    return "; ".join(problems[:limit]) + (f"; and {len(problems) - limit} more" if len(problems) > limit else "")


def same_address(url: str) -> str:
    """An address as `capture` records it and a board links it, for comparing: no fragment, the scheme and the host in lower case and without the port of its scheme (what the browser's URL gives: ":443" on
    https is dropped, ":8443" is kept), and no trailing slash."""
    url = url.strip().split("#", 1)[0]
    try:
        parts = urlsplit(url)
        scheme, netloc = parts.scheme.lower(), parts.netloc.lower()
        port = DEFAULT_PORTS.get(scheme)
        if port and netloc.endswith(port):
            netloc = netloc[:-len(port)]
        url = urlunsplit((scheme, netloc, parts.path, parts.query, ""))
    except ValueError:
        pass
    return url[:-1] if url.endswith("/") else url


def top_items(node: Node) -> list[Node]:
    """The <li> of a list at its own level: those under the node that sit in no other <li> of it. A list inside a reference's take, or inside a site's reason, is part of that item, not more items."""
    found: list[Node] = []

    def visit(n: Node) -> None:
        for c in n.children:
            if c.tag == "li":
                found.append(c)
            else:
                visit(c)

    visit(node)
    return found


def has_words(node: Node, fid: str) -> bool:
    """A field of a reference (data-field="take" or "avoid") holds words of the author's: the label the template puts inside it ("Take:", "Avoid:") is not one, so once the [[fill: ...]] marker is deleted
    a field that keeps only its label is empty. An image or other media counts, as it does for every field."""
    text = FIELD_LABELS[fid].sub("", node.text(skip_headings=True), count=1).strip()
    return (re.search(r"\w", text) is not None and not PLACEHOLDER.match(text)) or node.has_media()   # a dash or a dot left behind is not a word


def read_captures(rep: Report, project: Path) -> tuple[list[dict], list[str]]:
    """Every research/site-refs/<name>/capture.json: ({"folder", "addresses" (same_address of source.url and source.final_url), "url", "date", "hashes" (sha256 -> file of a thumbnail or a view)}, ...) and the
    files that could not be read. Each one that exists is an input of the lint report, so a capture made or made again later makes the lint stale."""
    found, unreadable = [], []
    for f in sorted(Path(project).glob(CAPTURES)):
        if not f.is_file():
            continue
        rep.inputs.append(f)
        folder = rel(project, f.parent)
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
            source = doc["source"]
            urls = [u for u in (source.get("url"), source.get("final_url")) if isinstance(u, str) and u.strip()]
            hashes = {e["sha256"]: e.get("file", "") for key in ("thumbs", "views") for e in doc.get(key, []) if isinstance(e, dict) and isinstance(e.get("sha256"), str)}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            unreadable.append(f"{folder}/capture.json")
            continue
        found.append({"folder": folder, "url": urls[0] if urls else "", "addresses": {same_address(u) for u in urls}, "date": str(doc.get("date", "")), "hashes": hashes})
    return found, unreadable


def link_of(node: Node) -> Node | None:
    """The link to the site: the first <a href> under the node, when its address is http(s). A site that links to a page of its own (/x, #x, mailto:) has no link, even when the text beside it holds an http
    address: the first link is the site's, and any later one belongs to the take, the reason or the caption."""
    first = next((n for n in node.walk() if n.tag == "a" and "href" in n.attrs), None)
    return first if first is not None and HTTP_LINK.match(first.attrs["href"].strip()) else None


def shot_row(rep: Report, project: Path, page: Path, rid: str, shot: Node, href: str, captures: list[dict], unreadable: list[str]) -> None:
    """group:<name>:shot:<k>: the screenshot of a reference is the thumbnail or a view of a capture of the address the reference links to. A match passes; anything else warns (never fails): the picture may be
    a screenshot the owner sent, but the board has to say so in its caption, and the lead is told where the picture came from."""
    fix = CAPTURE_FIX.format(href=href or "<address>")
    src = shot.attrs.get("src", "").strip()
    if not href:
        rep.add(rid, "warn", SHOT_LABEL, detail=f"not matched to a capture: the reference links to no http(s) address to match it with ({fix})")
        return
    if src[:5].lower() != "data:":
        rep.add(rid, "warn", SHOT_LABEL, detail=f"not matched to a capture of {href}: the src is not an inlined data: image, so there are no bytes to compare (the references row says what to fix)")
        return
    data, why = motionboard.shown_bytes(Path(project), page, src)
    if data is None:
        rep.add(rid, "warn", SHOT_LABEL, detail=f"not matched to a capture of {href}: the src {why}")
        return
    digest, want = sha256_bytes(data), same_address(href)
    elsewhere = None
    for c in captures:
        if digest in c["hashes"]:
            if want in c["addresses"]:
                rep.add(rid, "pass", SHOT_LABEL, detail=f"{c['hashes'][digest] or 'a picture'} of {c['folder']}/capture.json" + (f", captured {c['date']}" if c["date"] else ""))
                return
            elsewhere = elsewhere or c
    of_address = next((c for c in captures if want in c["addresses"]), None)
    tail = (f" (the picture is a capture of {elsewhere['url'] or elsewhere['folder']}, in {elsewhere['folder']}/capture.json)" if elsewhere is not None else
           f" ({of_address['folder']}/capture.json holds a capture of that address, and this picture is none of its views or thumbnails)" if of_address is not None else
           " (no capture.json under research/site-refs/ holds that address)" if captures else " (there is no research/site-refs/<name>/capture.json)")
    if unreadable:
        tail += f"; could not be read: {', '.join(unreadable[:3])}"
    rep.add(rid, "warn", SHOT_LABEL, detail=f"not matched to a capture of {href}{tail}: {fix}")


def reference_problems(k: int, li: Node) -> tuple[list[str], Node | None, str]:
    """(what is missing from reference k of a group, its first screenshot, its address). A reference is an <li> with a link to the site (http or https), a screenshot (<img data-field="shot">, held to the rule of
    a thumbnail: inlined, alt text, in a <figure> with a caption that is more than the template's " · shown for private research"), a data-field="take" and a data-field="avoid" that hold words beyond the
    label the template puts in them (has_words)."""
    link = link_of(li)
    name = re.sub(r"\s+", " ", link.text()).strip()[:40] if link is not None else ""
    shots = [n for n in li.walk() if n.attrs.get("data-field") == "shot"]
    problems = [] if link is not None else ["no link to the site (an <a href=\"https://...\">)"]
    if not shots:
        problems.append('no screenshot (<img data-field="shot">)')
    else:
        problems += thumb_problems(shots[0], field="shot", subject="the screenshot", says="whose site it is and when it was captured", template_tail=CAPTION_TAIL)
    for fid, what in (("take", "what to take"), ("avoid", "what to avoid")):
        if not any(has_words(n, fid) for n in li.find_all(data_field=fid)):
            problems.append(f'no {what} (data-field="{fid}" missing, empty, or only the label "{fid.capitalize()}:")')
    who = f"reference {k}" + (f" ({name})" if name else "")
    return [f"{who}: {p}" for p in problems], (shots[0] if shots else None), (link.attrs["href"].strip() if link is not None else "")


def group_rows(rep: Report, project: Path, page: Path, root: Node) -> None:
    """For each group of the page: group:<name>:name (a word, unique, not a label), :idea (how the group serves the visitor's job), :references (three or more <li> of the list itself, each with a link, a screenshot, what to take and what to
    avoid; the detail names what is missing per reference), :layout (only when the group declares data-layout: an id of page-layouts.json passes, own:<word> warns, anything else fails naming the ids) and, for
    each reference that has a screenshot, :shot:<k> (see shot_row). A group without a name is listed by its place, #n. Every capture.json read is an input of the report."""
    captures, unreadable = read_captures(rep, project)
    layouts: dict[str, dict] | None = None
    seen: list[str] = []
    for i, g in enumerate(sections(root, "group"), 1):
        nm = g.attrs.get("data-name", "").strip()
        gid = f"group:{nm or f'#{i}'}"
        if not WORD_NAME.match(nm) or GENERIC_NAME.match(nm) or GENERIC_GROUP.match(nm):
            rep.add(f"{gid}:name", "fail", "word name", detail='data-name must be a word of 3+ letters (not "A", "Option 2", "Group II")')
        elif nm.lower() in seen:
            rep.add(f"{gid}:name", "fail", "word name", detail="duplicate group name")
        else:
            rep.add(f"{gid}:name", "pass", "word name")
        seen.append(nm.lower())

        ideas = list(g.find_all(data_field="idea"))
        ok = any(n.nonempty() for n in ideas)
        rep.add(f"{gid}:idea", "pass" if ok else "fail", "how the group serves the visitor's job",
                detail="ok" if ok else 'missing or empty: data-field="idea" inside the group (one sentence: how these sites serve the job, not what they look like)')

        items = [li for r in g.find_all(data_field="references") for li in top_items(r)]
        problems, shots = [], []
        for k, li in enumerate(items, 1):
            found, shot, href = reference_problems(k, li)
            problems += found
            shots.append((k, shot, href))
        if len(items) < MIN_REFERENCES:
            problems.insert(0, f"{len(items)} reference(s); a group needs at least {MIN_REFERENCES} real sites (each <li> in data-field=\"references\")")
        rep.add(f"{gid}:references", "fail" if problems else "pass", f"{MIN_REFERENCES}+ sites, each with a link, a screenshot, what to take and what to avoid",
                detail=shown(problems) if problems else f"{len(items)} reference(s)")
        for k, shot, href in shots:
            if shot is not None:
                shot_row(rep, project, page, f"{gid}:shot:{k}", shot, href, captures, unreadable)

        if "data-layout" in g.attrs:
            value = g.attrs["data-layout"].strip()
            label = "layout is a reference of page-layouts.json"
            if OWN_LAYOUT.fullmatch(value):
                rep.add(f"{gid}:layout", "warn", label, detail=f"{value}: a layout of its own; say in the idea why none of the references fits")
            else:
                layouts = sitedata.load_layouts() if layouts is None else layouts   # read once, and only when a group names a layout
                if value in layouts:
                    rep.add(f"{gid}:layout", "pass", label, detail=f"{value}: {layouts[value]['job']}")
                else:
                    rep.add(f"{gid}:layout", "fail", label, detail=f"data-layout={value!r} is no layout: use one of {', '.join(layouts)}, or own:<word> with the reason in the idea")


def owner_rows(rep: Report, root: Node) -> None:
    """owner-sites:items. Every <li> of the owner-sites section is a site the owner named: data-like is "like" or "dislike", it has an http(s) link or an inlined image (a screenshot the owner sent), and a non-empty
    data-field="why". A section with no <li> is the owner naming none: it passes when it has text (the section row fails when it has none)."""
    label = "each site the owner named is liked or disliked, has a link or a picture, and says why"
    section = next((n for n in sections(root, "owner-sites") if n.nonempty()), None)
    if section is None:
        return
    items = top_items(section)
    if not items:
        rep.add("owner-sites:items", "pass", label, detail="no site listed: the owner named none, and the section says so")
        return
    problems = []
    for k, li in enumerate(items, 1):
        link = link_of(li)
        name = re.sub(r"\s+", " ", link.text() if link is not None else li.text()).strip()[:40]
        who = f"site {k}" + (f" ({name})" if name else "")
        like = li.attrs.get("data-like", "").strip()
        if like not in ("like", "dislike"):
            problems.append(f'{who}: data-like is {like!r}, it must be "like" or "dislike"' if "data-like" in li.attrs else f'{who}: no data-like ("like" or "dislike")')
        if link is None and not any(n.tag == "img" and DATA_IMAGE.match(n.attrs.get("src", "").strip()) for n in li.walk()):
            problems.append(f"{who}: no http(s) link and no inlined image of the site")
        if not any(n.nonempty() for n in li.find_all(data_field="why")):
            problems.append(f'{who}: no reason (data-field="why" missing or empty, in the owner\'s words)')
    kinds = [li.attrs.get("data-like", "").strip() for li in items]
    rep.add("owner-sites:items", "fail" if problems else "pass", label,
            detail=shown(problems) if problems else f"{len(items)} site(s): {kinds.count('like')} liked, {kinds.count('dislike')} disliked")
