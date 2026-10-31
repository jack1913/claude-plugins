"""The rows of the website references board (data-board="site-refs"): a round after G4 that shows the owner groups of real sites to learn from, before any page of the site is built.

The board is an ordinary round (rounds/rN/board.html, N 2 or more), from templates/site-refs-board.html. This file holds the rows that need more than the page: the gates of the work
(refs_gate_rows: site-refs:tier, site-refs:brief, site-refs:g4, site-refs:research, site-refs:cliches-file) and the reading of brief/BRIEF.md that decides whether the project has a
site at all (brief_lists_site). The sections, the group count and the page rules are board_lint's own, with the other kinds of board. The site board (data-board="site", templates/site-board.html) has its rows here too: the gates of
the site round (site_gate_rows: site:tier, site:brief, site:g4, site:g4w) and, at the hero stage, one card per variant (variant_rows: site:variants, site:files, site:layout, site:fields) and the proof each variant brings: the page-check report of its page (site:check), the tells in it (site:tells) and the stills `capture` took (site:stills).

Whether the brief lists a site is read from the value after "Required surfaces:" in brief/BRIEF.md, against a list of English and Polish words (SITE_WORDS). A value wrapped in parentheses is the untouched
line of the template ("(site, app icon, ...)"), the owner's own words not yet written, and does not count. A brief in another language is not recognised: the owner adds the word "site" to the line.

The folder of boardlib is outside scripts/lib/, so a change here does not make every pack stale. Standard library only (plus _common, reflex and `report_tool` of scripts/pagelib/pagecheck.py, the one rule that names the report of a page); no clock and no network. The reads are the named files, the reports and the stills of each variant.
"""
from __future__ import annotations

import base64
import binascii
import json
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote, unquote_to_bytes

from _common import CliError, Report, confine, gate_recorded, list_rounds, read_state, rel, sha256_bytes, sha256_file, stale_inputs
from boardpage import FILL, GENERIC_NAME, WORD_NAME, Node, is_site_refs_board, page_kind, page_marker, read_page
from pagecheck import report_tool   # scripts/pagelib/pagecheck.py: the name of the report of one page, never a copy of the rule
import reflex
from sitedata import load_layouts

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


# ---------------------------------------------------------------- the site board (data-board="site"): the gates of the site round, and the hero variants

SITE_ATTR = "data-site-variant"
STAGES = ("hero", "pages")          # data-site-stage: the hero variants first, then the other pages
FIRST_COUNT = (2, 3)                # the first hero board of a project shows this many variants; a later one (the refine loop) shows one or more
FOLDER_NAME = re.compile(r"[A-Za-z0-9_-]+")      # the name is also the folder rounds/rN/<name>/
PAGE_ID = re.compile(r"[a-z][a-z0-9-]{1,31}")    # <body data-page>: the id the page gets in site/ (site/<id>/index.html)
OWN_LAYOUT = re.compile(r"own:[a-z][a-z0-9-]*")  # a layout of the page's own: the references are not a menu of templates
SKIPPED = "skipped by owner"        # what G4w says when the owner skipped the website references, in their own words
RECORD_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}\s*")   # `state --record` writes "<date> <decision>"
FIELDS = (("what-it-is", "What it is"), ("from-refs", "Takes from"), ("cost", "Cost"))
TELL_ROW = re.compile(r"^tell:([a-z0-9-]+)$")    # the row page-check gives a generic tell of skills/brand-creator/references/page-tells.json (pagecheck.tell_rows): a warning when it found one
VIEWS = ("1440-light", "1440-dark", "390-light", "390-dark")   # the four first-screen stills `capture <page>` takes, and the four a card shows
SHA256 = re.compile(r"[0-9a-f]{64}")


def stage_of(root: Node | None) -> str | None:
    """The data-site-stage the page declares ("" when it declares none), read from the element that declares the kind and the round, or None when no tag does."""
    marker = page_marker(root) if root is not None else None
    return marker.attrs.get("data-site-stage", "").strip() if marker is not None else None


def is_first(project: Path, rnd: int, stage: str | None) -> bool:
    """Whether the board of round `rnd` is the first site board of its stage in the project: no earlier round holds a site board that declares the same stage."""
    for n, d in list_rounds(project):
        if n < rnd:
            root = read_page(d / "board.html")
            if page_kind(root) == "site" and stage_of(root) == stage:
                return False
    return True


def references_board(project: Path, rnd: int) -> tuple[int, Path] | None:
    """(the round, its board) of the latest website references board before round `rnd` that counts (boardpage.is_site_refs_board), or None."""
    found = [(n, d / "board.html") for n, d in list_rounds(project) if n < rnd and is_site_refs_board(read_page(d / "board.html"), n)]
    return found[-1] if found else None


def site_gate_rows(rep: Report, project: Path, rnd: int) -> None:
    """site:tier (Standard or Full), site:brief (the brief lists a site), site:g4 (the system rules are approved) and site:g4w (the owner picked from the website references, or skipped them in their own words;
    a pick needs the references board in an earlier round). The lint report lists the brief, and the references board that G4w stands on, as inputs, so a change to either makes it stale."""
    brief = Path(project) / BRIEF_FILE
    if brief.is_file():
        rep.inputs.append(brief)
    state = read_state(project)

    tier = str(state.get("tier", "") or "").strip().lower()
    rep.add("site:tier", "pass" if tier in TIERS else "fail", "the site round is Standard and Full",
            detail=f"tier: {tier}" if tier in TIERS else f"the site round is Standard and Full (this project's tier is {tier or 'missing'}): it is not offered in the Quick tier")

    listed, why = brief_lists_site(project)
    rep.add("site:brief", "pass" if listed else "fail", "the brief lists a site",
            detail=why if listed else f"the site round runs only when {BRIEF_FILE} lists a site under Required surfaces, in the owner's words; ask the owner ({why})")

    g4 = gate_recorded(project, "G4")
    rep.add("site:g4", "pass" if g4 else "fail", "the site round comes after the system rules (G4)",
            detail=f"G4: {g4}" if g4 else "the site round comes after the system rules (G4): record the owner's approval first (`brand-creator state --record G4 \"<decision>\"`)")

    g4w = gate_recorded(project, "G4w")
    label = "the site round follows the owner's pick of website references (G4w), or their skip"
    if not g4w:
        rep.add("site:g4w", "fail", label, detail="the site round waits for the owner's pick of website references (G4w): show the references board (`/brand-creator:round site-refs`) and record the pick "
                                                  "(`brand-creator state --record G4w \"picked <groups>\"`), or, when the owner skips the references in their own words, `state --record G4w \"skipped by owner\"`")
    elif RECORD_DATE.sub("", g4w).lower().startswith(SKIPPED):
        rep.add("site:g4w", "pass", label, detail=f"G4w: {g4w}")
    else:
        found = references_board(project, rnd)
        if found is None:
            rep.add("site:g4w", "fail", label, detail=f"G4w names a pick but no website references board came before this round (G4w: {g4w}): a round before r{rnd} with data-board=\"site-refs\", its own round "
                                                      "and at least four groups; or the owner skipped the references in their own words (`state --record G4w \"skipped by owner\"`)")
        else:
            rep.inputs.append(found[1])
            rep.add("site:g4w", "pass", label, detail=f"G4w: {g4w}; the references board is r{found[0]}")


class SiteVariant:
    """One variant of a hero board: its name, its card on the page, where its files are (project-relative, posix) and what its page declares on <body>."""

    def __init__(self, project: Path, rnd: int, name: str, card: Node):
        self.name, self.card = name, card
        self.dir = f"rounds/r{rnd}/{name}"
        self.page = f"{self.dir}/index.html"
        root = read_page(project / self.page)
        body = next((n for n in root.walk() if n.tag == "body"), None) if root is not None else None
        self.body = body.attrs if body is not None else None   # None: no page, or no <body> tag
        self.layout = self.body.get("data-layout", "").strip() if self.body is not None else ""
        self.page_id = self.body.get("data-page", "").strip() if self.body is not None else ""
        self.report = f"assets/_checks/{report_tool(self.page)}.json"   # what `brand-creator page-check <page>` wrote
        self.shots = f"{self.dir}/shots"                                # what `brand-creator capture <page>` wrote: the four stills and capture.json
        self.capture = f"{self.shots}/capture.json"


def cards(root: Node) -> list[Node]:
    """The variant cards of a page: every element that carries data-site-variant, in page order."""
    return [n for n in root.walk() if SITE_ATTR in n.attrs]


def shown(problems: list[str], limit: int = 6) -> str:
    return "; ".join(problems[:limit]) + (f"; and {len(problems) - limit} more" if len(problems) > limit else "")


def name_problems(found: list[Node], first: bool) -> tuple[list[str], list[tuple[str, Node]]]:
    """-> (what is wrong with the count and the names of the cards, the cards whose name can be a variant: (name, card))."""
    lo, hi = FIRST_COUNT
    problems: list[str] = []
    if first and not lo <= len(found) <= hi:
        problems.append(f"{len(found)} variant card(s) found, the first hero board of a project shows {lo} or {hi}")
    if not first and not found:
        problems.append("no variant card found, a later hero board shows 1 or more")
    named: list[tuple[str, Node]] = []
    seen: list[str] = []
    for i, card in enumerate(found, 1):
        nm = card.attrs.get(SITE_ATTR, "").strip()
        label = nm or f"#{i}"
        if not WORD_NAME.match(nm) or GENERIC_NAME.match(nm):
            problems.append(f'{label}: {SITE_ATTR} must be a word of 3+ letters (not "A", "Variant 2", "Option B")')
        elif not FOLDER_NAME.fullmatch(nm):
            problems.append(f"{label}: the name is also the folder rounds/rN/<name>/: letters, digits, - and _ only")
        elif nm.lower() in seen:
            problems.append(f"{nm}: duplicate variant name")
        else:
            named.append((nm, card))
        seen.append(nm.lower())
    return problems, named


def spelling_problem(project: Path, v: SiteVariant, rnd: int) -> str | None:
    """The folder of a variant is there under the very name the card has, letter case included, as the round's folder lists it. A disk that does not tell letter cases apart (macOS, Windows) opens
    rounds/rN/Ledger/ for a folder called ledger, but the reports of `page-check` and `capture` are named after the page's path as it is written, so the reports this board asks for (named after the card) would
    never be found: read from the listing, the folder is wrong in the same words on every kind of disk. None when it is spelt alike, or when there is no folder at all (files_problems says that)."""
    try:
        listed = sorted(e.name for e in (project / "rounds" / f"r{rnd}").iterdir())
    except OSError:
        return None
    alike = [e for e in listed if e.lower() == v.name.lower()]
    if v.name in listed or not alike:
        return None
    return (f"{v.name}: the card and its folder must be spelt alike, letter case included: the card says {v.name}, the folder is rounds/r{rnd}/{alike[0]}/ (rename one to match the other: "
            "the reports of `page-check` and `capture` are named after the page's path, so a card spelt otherwise never finds them)")


def link_problem(v: SiteVariant, page_rel: str, rnd: int) -> str | None:
    """The card links the live page: an <a data-field="live"> with an href; on the board of the round itself (rounds/rN/board.html) it leads to the variant's index.html."""
    links = list(v.card.find_all(data_field="live"))
    href = links[0].attrs.get("href", "").strip() if links else ""
    if not href:
        return f'{v.name}: the card has no link to the live page (<a data-field="live" href="{v.name}/index.html">)'
    if posixpath.dirname(page_rel) == f"rounds/r{rnd}":
        target = posixpath.normpath(posixpath.join(f"rounds/r{rnd}", re.split(r"[?#]", href, maxsplit=1)[0]))
        if target != v.page:
            return f"{v.name}: the live link {href!r} does not lead to {v.page}"
    return None


def files_problems(project: Path, v: SiteVariant, page_rel: str, rnd: int) -> list[str]:
    """site:files: the folder (spelt as the card spells it), its index.html, the <body> of that page declaring data-layout and data-page (a page id), and the live link of the card."""
    spelling = spelling_problem(project, v, rnd)
    if spelling:
        return [spelling]
    if not (project / v.dir).is_dir():
        return [f"{v.name}: {v.dir}/ does not exist (one folder per variant: index.html, and the stills and the record of `brand-creator capture {v.page}` in shots/)"]
    out = []
    if not (project / v.page).is_file():
        out.append(f"{v.name}: {v.page} is missing (the home page's first screen, built from the picked references)")
    elif v.body is None:
        out.append(f'{v.name}: {v.page} has no <body> tag (it declares data-layout and data-page there: <body data-layout="walkthrough" data-page="start">)')
    else:
        if not v.layout:
            out.append(f'{v.name}: the <body> of {v.page} declares no data-layout (an id of page-layouts.json, or own:<word>)')
        if not v.page_id:
            out.append(f'{v.name}: the <body> of {v.page} declares no data-page (the id the page gets in site/, for the home page "start")')
        elif not PAGE_ID.fullmatch(v.page_id):
            out.append(f"{v.name}: data-page {v.page_id!r} in {v.page} is not a page id (lowercase letters, digits and -, 2 to 32 characters, starting with a letter)")
    link = link_problem(v, page_rel, rnd)
    return out + ([link] if link else [])


def layout_problems(v: SiteVariant, known: dict[str, dict]) -> tuple[list[str], list[str]]:
    """site:layout for one variant -> (failures, warnings). The page's data-layout is an id of page-layouts.json (pass), or own:<word> (a warning: say on the card why none of the references fit); anything
    else, or none, fails. The card says the same: its data-field="layout" carries a data-layout equal to the page's."""
    failures: list[str] = []
    warnings: list[str] = []
    if not v.layout:
        failures.append(f"{v.name}: the page declares no data-layout, so no layout reference is recorded (an id of page-layouts.json, or own:<word>)")
    elif v.layout in known:
        pass
    elif OWN_LAYOUT.fullmatch(v.layout):
        warnings.append(f"{v.name}: a layout of its own ({v.layout}): say on the card why none of the references fit")
    else:
        failures.append(f"{v.name}: data-layout {v.layout!r} is no id of page-layouts.json (known: {', '.join(known)}) and no own:<word>")
    lines = list(v.card.find_all(data_field="layout"))
    said = lines[0].attrs.get("data-layout", "").strip() if lines else ""
    if not lines:
        failures.append(f'{v.name}: the card has no layout line (<p data-field="layout" data-layout="{v.layout or "<id>"}">)')
    elif not said:
        failures.append(f'{v.name}: the layout line of the card carries no data-layout (the page says {v.layout or "none"})')
    elif v.layout and said != v.layout:
        failures.append(f"{v.name}: the card says data-layout {said!r} and the page says {v.layout!r}")
    return failures, warnings


def field_problems(v: SiteVariant) -> list[str]:
    """What it is, Takes from and Cost are filled in: some text, no placeholder and no [[fill: ...]] marker left."""
    out = []
    for fid, label in FIELDS:
        nodes = list(v.card.find_all(data_field=fid))
        text = " ".join(n.text() for n in nodes)
        if not any(n.nonempty() for n in nodes):
            out.append(f'{v.name}: {label} is missing or empty (data-field="{fid}" inside the card)')
        elif FILL in text:
            out.append(f"{v.name}: {label} still holds a [[fill: ...]] marker")
    return out


# ---------------------------------------------------------------- the proof of each variant: page-check, its tells, and the stills

def read_record(project: Path, where: str, page: str) -> tuple[dict | None, list[str]]:
    """The JSON record at `where` (a page-check report, or capture.json), read as `check` reads one: (its document, why it no longer stands for the page). Why: a file it was made from is gone or
    changed (_common.stale_inputs, the rule `check` applies), or the page itself is not among them (a change to the page would then never make it stale). The document is None when it cannot be read."""
    try:
        doc = json.loads((project / where).read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            return None, ["it is not a JSON object"]
        stale = stale_inputs(project, doc)
        listed = {r.get("path") for r in doc.get("inputs", []) if isinstance(r, dict)}
    except (OSError, ValueError, AttributeError, KeyError, TypeError) as e:
        return None, [f"it cannot be read ({type(e).__name__}: {e})"]
    if page not in listed:
        stale.append(f"it does not list {page} among the files it was made from, so a change to the page would not show")
    return doc, stale


def made_from(project: Path, where: str) -> list[Path]:
    """The files the record at `where` was made from, its own `inputs`: the page and every file the browser was served. A record that is missing or cannot be read lists none: the rows say so."""
    try:
        return [project / rec["path"] for rec in json.loads((project / where).read_text(encoding="utf-8"))["inputs"] if isinstance(rec, dict) and isinstance(rec.get("path"), str)]
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        return []


def listed_stills(project: Path, v: SiteVariant) -> list[Path]:
    """The files capture.json names for the four views, whatever they are called. A capture.json that is missing or cannot be read lists none: site:stills says so."""
    try:
        views = json.loads((project / v.capture).read_text(encoding="utf-8"))["views"]
        return [project / v.shots / e["file"] for e in views if isinstance(e, dict) and isinstance(e.get("file"), str) and "/" not in e["file"] and "\\" not in e["file"]]
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        return []


def one_line(text, limit: int = 240) -> str:
    s = re.sub(r"\s+", " ", str(text)).strip()
    return s if len(s) <= limit else s[:limit - 3].rstrip() + "..."


def target_words(target) -> str:
    """What a page-check report says it is the report of, in words (for a report of another page, or of a built site or an address)."""
    if not isinstance(target, dict):
        return "no target"
    return f"{target.get('kind')} {target.get('page') or target.get('url') or target.get('from')}"


def check_problems(project: Path, v: SiteVariant) -> tuple[list[str], dict | None]:
    """site:check for one variant -> (the problems, the report when it is a current verdict, else None). The report of its page (`brand-creator page-check <page>`, found by the page's path) is there, it is the
    report of this very page of the project, it is current, and it is a verdict (pass or fail); the check line of the card (data-check) says that status and has text. A failing check shown as `fail` is honest and passes."""
    cmd = f"brand-creator page-check {v.page}"
    problems: list[str] = []
    verdict: dict | None = None
    status = None
    if not (project / v.report).is_file():
        problems.append(f"{v.name}: no page-check report of {v.page}: run `{cmd}`")
    else:
        doc, stale = read_record(project, v.report, v.page)
        target = doc.get("target") if doc is not None else None
        if doc is not None and not (isinstance(target, dict) and target.get("kind") == "project" and target.get("page") == v.page):
            stale.insert(0, f"it is the report of {target_words(target)}, not of the project page {v.page}")
        if stale:
            problems.append(f"{v.name}: the page-check report is stale ({shown(stale, 3)}): run `{cmd}`")
        elif doc.get("status") not in ("pass", "fail"):
            rows = [r for r in (doc.get("results") if isinstance(doc.get("results"), list) else []) if isinstance(r, dict) and r.get("status") == "skipped"]
            said = " | ".join(f"{r.get('id')}: {one_line(r.get('detail', ''))}" for r in rows[:3]) + (f" | and {len(rows) - 3} more" if len(rows) > 3 else "")
            problems.append(f"{v.name}: the page-check report is {doc.get('status')!r}, not a verdict ({said or 'it lists no row that is not verified'}): change the page or the setup as the rows say, then run `{cmd}`")
        else:
            verdict, status = doc, doc["status"]
    lines = [n for n in v.card.walk() if "data-check" in n.attrs]
    if len(lines) != 1:
        problems.append(f'{v.name}: the card needs one check line (data-check="pass" or "fail" and its text), it has {len(lines)}')
        return problems, verdict
    claimed = lines[0].attrs["data-check"].strip()
    if claimed not in ("pass", "fail"):
        problems.append(f'{v.name}: data-check must be "pass" or "fail", got {claimed!r}')
    elif status is not None and claimed != status:
        problems.append(f'{v.name}: the card says data-check="{claimed}" and the page-check report says {status}')
    if not lines[0].nonempty():
        problems.append(f"{v.name}: the check line has no text")
    return problems, verdict


def tells_found(doc: dict) -> list[tuple[str, str]]:
    """The generic tells a page-check report warns of: (the tell's id, its name), one per `warn` row whose id is tell:<id>, in the report's order."""
    rows = doc.get("results") if isinstance(doc.get("results"), list) else []
    found = []
    for r in rows:
        m = TELL_ROW.fullmatch(str(r.get("id", ""))) if isinstance(r, dict) and r.get("status") == "warn" else None
        if m:
            found.append((m.group(1), one_line(r.get("label", ""), 80)))
    return found


def tells_problems(v: SiteVariant, doc: dict) -> list[str]:
    """site:tells for one variant: every tell its page-check report warns of is named, by its id, on the card's tells line (data-field="tells")."""
    text = " ".join(n.text() for n in v.card.find_all(data_field="tells"))
    missing = [(tid, name) for tid, name in tells_found(doc) if not re.search(rf"(?<![A-Za-z0-9-]){re.escape(tid)}(?![A-Za-z0-9-])", text, re.I)]
    if not missing:
        return []
    return [f"{v.name}: the card does not name {', '.join(f'{tid} ({name})' if name else tid for tid, name in missing)}, which page-check found: show every tell page-check found, "
            "with what you will do about it (name each by its id on the tells line, data-field=\"tells\")"]


def shown_bytes(project: Path, page: Path, src: str) -> tuple[bytes | None, str]:
    """The bytes of the picture a card shows: a data: URI decoded, or the project file a relative path names (read from the page's own folder, as a browser would).
    -> (bytes, "") or (None, why). A picture from the network, or by an absolute path, is not the project's file."""
    src = src.strip()
    if not src:
        return None, "has no src"
    if src[:5].lower() == "data:":
        head, comma, body = src.partition(",")
        if not comma:
            return None, "is a data: URI with no data"
        try:
            return (base64.b64decode(body, validate=True) if head.lower().endswith(";base64") else unquote_to_bytes(body)), ""
        except (binascii.Error, ValueError):
            return None, "is a data: URI that cannot be decoded"
    if re.match(r"(?:[a-z][a-z0-9+.-]*:|/)", src, re.I):
        return None, f"is {src[:48]!r}: a site board shows the project's own file by a relative path, or a data: URI (nothing from the network)"
    try:
        f = confine(project, page.parent / unquote(re.split(r"[?#]", src, maxsplit=1)[0]), what="picture")
    except CliError:
        return None, f"is {src[:48]!r}, which is outside the project (a site board shows the project's own files)"
    if not f.is_file():
        return None, f"names {rel(project, f)}, which does not exist"
    return f.read_bytes(), ""


def stills_problems(project: Path, page: Path, v: SiteVariant) -> list[str]:
    """site:stills for one variant: shots/capture.json (`brand-creator capture <page>`) is there, it is the capture of this page, its inputs are current, it lists a sha256 for each of the four views, the file it
    names for a view is those bytes, and the card shows exactly one picture per view whose bytes are the listed ones (the file by its relative path, or a data: URI of the same bytes on the review copy)."""
    cmd = f"brand-creator capture {v.page}"
    if not (project / v.capture).is_file():
        return [f"{v.name}: no {v.capture}, so the stills are not those of the page: run `{cmd}`"]
    doc, stale = read_record(project, v.capture, v.page)
    if doc is None:
        return [f"{v.name}: {v.capture} is unusable ({shown(stale, 2)}): run `{cmd}`"]
    out: list[str] = []
    source = doc.get("source")
    if not (isinstance(source, dict) and source.get("page") == v.page):
        of = (source.get("page") or source.get("url")) if isinstance(source, dict) else None
        out.append(f"{v.name}: {v.capture} is the capture of {of}, not of {v.page} (a folder copied from an earlier round): run `{cmd}`")
    if stale:
        out.append(f"{v.name}: {v.capture} is stale ({shown(stale, 3)}): run `{cmd}`")
    listed = {e.get("view"): e for e in doc.get("views", []) if isinstance(e, dict)} if isinstance(doc.get("views"), list) else {}
    imgs = [n for n in v.card.find_all(data_field="still") if n.tag == "img"]
    for extra in (n for n in imgs if n.attrs.get("data-view", "").strip() not in VIEWS):
        out.append(f'{v.name}: a still of the card has data-view {extra.attrs.get("data-view", "").strip()!r}, the views are {", ".join(VIEWS)}')
    for view in VIEWS:
        entry = listed.get(view)
        want = entry.get("sha256") if isinstance(entry, dict) else None
        if not (isinstance(want, str) and SHA256.fullmatch(want)):
            out.append(f"{v.name}: {v.capture} lists no {view} still with a sha256: run `{cmd}`")
            continue
        name = entry.get("file")
        if not (isinstance(name, str) and name and "/" not in name and "\\" not in name and name not in (".", "..")):
            out.append(f"{v.name}: {v.capture} names {name!r} for the {view} still, which is no file of {v.shots}/: run `{cmd}`")
            continue
        f = project / v.shots / name
        if not f.is_file():
            out.append(f"{v.name}: {v.shots}/{name} (the {view} still) is not there: run `{cmd}`")
        elif sha256_file(f) != want:
            out.append(f"{v.name}: {v.shots}/{name} is not the {view} still {v.capture} lists (its sha256 differs): run `{cmd}`")
        mine = [n for n in imgs if n.attrs.get("data-view", "").strip() == view]
        if len(mine) != 1:
            out.append(f'{v.name}: the card needs one <img data-field="still" data-view="{view}">, it has {len(mine)}')
            continue
        data, why = shown_bytes(project, page, mine[0].attrs.get("src", ""))
        if data is None:
            out.append(f"{v.name}: the {view} picture {why}")
        elif sha256_bytes(data) != want:
            out.append(f"{v.name}: the {view} picture the card shows is not the one {v.capture} lists (sha256 {sha256_bytes(data)[:12]} against {want[:12]}): show {v.shots}/{name}, taken by `{cmd}`")
    return out


def proof_rows(rep: Report, project: Path, page: Path, variants: list[SiteVariant]) -> None:
    """site:check, site:tells and site:stills for the variants of a hero board: each is one result for the whole board and names the variants it fails. Without a variant card they are not verified. site:tells
    reads the report that site:check found current: a variant with no such report is not judged here (site:check says why), so a board with nothing else wrong in the tells is "not verified", never a pass."""
    labels = (("site:check", "each variant's page-check is current and the card says what it found"), ("site:tells", "the card names every tell page-check found"),
              ("site:stills", "the stills on the cards are those `capture` took of the page as it is now"))
    if not variants:
        for rid, label in labels:
            rep.add(rid, "skipped", label, detail="not verified: there is no variant card to look at (site:variants says why)")
        return
    checks = [check_problems(project, v) for v in variants]
    rep.add("site:check", "fail" if any(p for p, _ in checks) else "pass", labels[0][1],
            detail=shown([x for p, _ in checks for x in p]) if any(p for p, _ in checks) else "a current page-check verdict each, and the check line of each card says its status")
    judged = [(v, doc) for v, (_, doc) in zip(variants, checks) if doc is not None]
    unread = [v.name for v, (_, doc) in zip(variants, checks) if doc is None]
    told = [x for v, doc in judged for x in tells_problems(v, doc)]
    if told:
        rep.add("site:tells", "fail", labels[1][1], detail=shown(told))
    elif unread:
        rep.add("site:tells", "skipped", labels[1][1], detail=f"not verified: no current page-check verdict to read the tells from for {', '.join(unread)} (site:check says why)")
    else:
        count = sum(len(tells_found(doc)) for _, doc in judged)
        rep.add("site:tells", "pass", labels[1][1], detail=(f"{count} tell(s) found by page-check, each named on its card" if count else "page-check found no tell"))
    problems = [x for v in variants for x in stills_problems(project, page, v)]
    rep.add("site:stills", "fail" if problems else "pass", labels[2][1],
            detail=shown(problems) if problems else "the four stills of each card are the files `capture` took of the page as it is now, byte for byte")
    for v in variants:   # the report of the lint is stale as soon as one of these changes: `check` re-reads their hashes
        rep.inputs += [project / v.report, project / v.capture] + [project / v.shots / f"{view}.png" for view in VIEWS]
        rep.inputs += made_from(project, v.report) + made_from(project, v.capture) + listed_stills(project, v)   # the files the two records were made from (the page, tokens.css, a stylesheet, a script), and the stills by the names capture.json gives


def variant_rows(rep: Report, project: Path, rnd: int, root: Node, page: Path, first: bool) -> None:
    """site:variants, site:files, site:layout and site:fields for the cards of a hero board (the first hero board of a project, `first`, shows two or three), then site:check, site:tells and site:stills (proof_rows).
    Each row is one result for the whole board and names the variants it fails. The lint report lists the index.html of each variant, its page-check report, its capture.json and its stills (and what those were made from) as inputs."""
    page_rel = rel(project, page)
    problems, named = name_problems(cards(root), first)
    lo, hi = FIRST_COUNT
    rep.add("site:variants", "fail" if problems else "pass", "the variants: their number, and a word for each",
            detail=shown(problems) if problems else f"{len(named)} variant(s): {', '.join(n for n, _ in named)}" + (f" (the first hero board: {lo} or {hi})" if first else ""))
    variants = [SiteVariant(project, rnd, nm, card) for nm, card in named]
    known = load_layouts()
    layouts = [layout_problems(v, known) for v in variants]
    failures, warnings = [p for f, _ in layouts for p in f], [p for _, w in layouts for p in w]
    rows = (("site:files", "each variant has its folder and page, and the page declares its layout and its id", [p for v in variants for p in files_problems(project, v, page_rel, rnd)],
             "folder, index.html, a <body> with data-layout and data-page, the live link of the card"),
            ("site:layout", "each page records a layout reference (or its own), and the card says the same", failures,
             "; ".join(f"{v.name}: {v.layout}" for v in variants)),
            ("site:fields", "each card says what it is, what it takes from the references and what it costs", [p for v in variants for p in field_problems(v)],
             "What it is, Takes from and Cost are filled in on every card"))
    for rid, label, found, ok in rows:
        if not variants:
            rep.add(rid, "skipped", label, detail="not verified: there is no variant card to look at (site:variants says why)")
        elif rid == "site:layout" and warnings and not found:   # a layout of its own is allowed, with a warning
            rep.add(rid, "warn", label, detail=shown(warnings))
        else:
            rep.add(rid, "fail" if found else "pass", label, detail=shown(found + (warnings if rid == "site:layout" else [])) if found else ok)
    proof_rows(rep, project, page, variants)
    for v in variants:   # the report of the lint is stale as soon as one of these changes: `check` re-reads their hashes
        rep.inputs.append(project / v.page)
