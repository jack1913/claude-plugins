"""The data of the site round: the layout references that ship with the plugin (skills/brand-creator/references/page-layouts.json).

A layout reference is keyed to what the visitor came to do and holds structure only: which part leads, the order of the parts, where the action sits
and how the page ends. A page records the one it used as <body data-layout="<id>">. `layout_problems` is the rule set the file must keep (a hex colour,
a number with a unit, a look word or the stock three-tiles-and-steps band in an item is a defect, so a reference never turns into a look or a template);
`load_layouts` reads the shipped file and returns the items by id, and stops with exit 3 naming the file when it cannot be used, because the file ships with the
plugin and a damaged install is the only way.

The pages the owner approved are kept in site/ with a record, site/site.json (schema 1, scripts/CONTRACT.md "site/site.json"). `load_site` reads it, `validate_site` says what is wrong with it
(the record itself, and each page file against the sha256 the record holds), and `rewrite_urls` is the rule that keeps a page's paths true when its folder moves from rounds/r<N>/<id>/ to
site/<id>/ (`brand-creator site approve`, scripts/site_pages.py); the same function carries a page into another folder later.

This folder is outside scripts/lib/, so a change here does not make every pack stale. Standard library only (plus _common for the error); no clock and no network.
The reads are the named files: the layout file, site/site.json and the pages it lists, and, for rewrite_urls, the existence of the files a page points at.
"""
from __future__ import annotations

import json
import os
import posixpath
import re
from pathlib import Path
from typing import Iterator, NamedTuple
from urllib.parse import quote, unquote

from _common import EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, CliError, sha256_file

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
LAYOUTS_FILE = "skills/brand-creator/references/page-layouts.json"   # from the plugin root
VERSION = 1
TOP_KEYS = ("version", "$description", "how_to_use", "items")
ITEM_KEYS = ("id", "job", "leads_with", "parts", "action", "ends_with", "not_for")
ID_PATTERN = re.compile(r"[a-z][a-z0-9-]{2,31}")
MIN_ITEMS, MAX_ITEMS = 8, 12
MIN_PARTS, MAX_PARTS = 2, 8
# What an item must not hold: a layout is structure, so the look is never in it.
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_UNIT = re.compile(r"\b\d+(?:\.\d+)?\s?(?:(?:px|rem|em|pt|vh|vw)\b|%)", re.I)
_LOOK_WORD = re.compile(r"\b(?:colou?rs?|fonts?|typefaces?|serif|gradients?|shadows?)\b", re.I)
_THREE, _STEPS = re.compile(r"\bthree\b", re.I), re.compile(r"\bsteps\b", re.I)
_USE_ATTR = "data-layout"   # how_to_use must tell the author how to record the choice


def _text(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _look_problems(where: str, value: str) -> list[str]:
    out = []
    for rx, what in ((_HEX, "a hex colour"), (_UNIT, "a number with a unit"), (_LOOK_WORD, "a look word")):
        m = rx.search(value)
        if m:
            out.append(f"{where} holds {what} ({m.group(0)!r}); a layout is structure only")
    return out


def layout_problems(doc) -> list[str]:
    """What is wrong with a page-layouts document, as sentences ([] when it is sound): the shape, 8-12 items with unique ids, the exact keys of each, 2-8 parts, no look
    value (a hex colour, a number with a unit, a look word) in any item, and no parts that hold both `three` and `steps` (the stock band is a tell, not a layout)."""
    if not isinstance(doc, dict):
        return [f"{LAYOUTS_FILE} is not an object"]
    problems = []
    if set(doc) != set(TOP_KEYS):
        problems.append(f"the top-level keys are {sorted(doc)}, not {sorted(TOP_KEYS)}")
    if doc.get("version") != VERSION:
        problems.append(f"version is {doc.get('version')!r}, not {VERSION}")
    if not _text(doc.get("$description")):
        problems.append("$description is missing or empty")
    how = doc.get("how_to_use")
    if not (isinstance(how, list) and how and all(_text(h) for h in how)):
        problems.append("how_to_use is not a list of sentences")
    elif _USE_ATTR not in " ".join(how):
        problems.append(f"how_to_use does not tell the author to record the choice as {_USE_ATTR}")
    items = doc.get("items")
    if not isinstance(items, list):
        return problems + ["items is not a list"]
    if not MIN_ITEMS <= len(items) <= MAX_ITEMS:
        problems.append(f"{len(items)} items; there are {MIN_ITEMS} to {MAX_ITEMS}")
    seen: set[str] = set()
    for n, item in enumerate(items, 1):
        if not isinstance(item, dict):
            problems.append(f"item {n} is not an object")
            continue
        iid = item.get("id")
        name = iid if isinstance(iid, str) and iid else f"item {n}"
        if set(item) != set(ITEM_KEYS):
            missing, extra = sorted(set(ITEM_KEYS) - set(item)), sorted(set(item) - set(ITEM_KEYS))
            problems.append(f"{name}: " + "; ".join(p for p in (f"missing {missing}" if missing else "", f"extra {extra}" if extra else "") if p) + f" (the keys are {list(ITEM_KEYS)})")
        if not (isinstance(iid, str) and ID_PATTERN.fullmatch(iid)):
            problems.append(f"{name}: the id does not match {ID_PATTERN.pattern}")
        elif iid in seen:
            problems.append(f"{name}: the id is used twice")
        else:
            seen.add(iid)
        strings: list[tuple[str, str]] = [("id", iid)] if isinstance(iid, str) else []
        for key in ("job", "leads_with", "action", "ends_with", "not_for"):
            if key in item:
                if _text(item[key]):
                    strings.append((key, item[key]))
                else:
                    problems.append(f"{name}: {key} is not a sentence")
        parts = item.get("parts")
        if "parts" in item:
            if not (isinstance(parts, list) and MIN_PARTS <= len(parts) <= MAX_PARTS and all(_text(p) for p in parts)):
                problems.append(f"{name}: parts is not a list of {MIN_PARTS} to {MAX_PARTS} non-empty strings")
            else:
                strings += [(f"parts[{i}]", p) for i, p in enumerate(parts)]
                joined = " ".join(parts)
                if _THREE.search(joined) and _STEPS.search(joined):
                    problems.append(f"{name}: parts hold both 'three' and 'steps', the stock band; a layout is not a template")
        for key, value in strings:
            problems += _look_problems(f"{name}: {key}", value)
    return problems


def load_layouts() -> dict[str, dict]:
    """The layout references of the plugin, by id, in file order. Exit 3 naming the file when it cannot be read or has problems: it ships with the plugin."""
    try:
        doc = json.loads((PLUGIN_ROOT / LAYOUTS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CliError(EXIT_CANNOT, f"{LAYOUTS_FILE} cannot be read ({e}): reinstall the plugin") from None
    problems = layout_problems(doc)
    if problems:
        shown = "; ".join(problems[:3]) + (f"; and {len(problems) - 3} more" if len(problems) > 3 else "")
        raise CliError(EXIT_CANNOT, f"{LAYOUTS_FILE} has problems ({shown}): reinstall the plugin")
    return {item["id"]: item for item in doc["items"]}


# ---------------------------------------------------------------- the record of the approved pages: site/site.json

SITE_DIR = "site"
SITE_FILE = "site/site.json"        # from the project root
SCHEMA = 1
SITE_KEYS = ("schema", "approved", "round", "hero", "pages", "choices")
SITE_PAGE_ID = re.compile(r"[a-z][a-z0-9-]{1,31}")   # a page id: the folder site/<id>/ and <body data-page> (the home page is "start")
OWN_LAYOUT = re.compile(r"own:[a-z][a-z0-9-]*")      # a layout of the page's own: the references are not a menu of templates
CHOICE_ID = re.compile(r"c[0-9]+")
TAGS = ("rule", "example")           # a rule says where the owner decided it; an example may change
SHA256 = re.compile(r"[0-9a-f]{64}")
RUN_AGAIN = "run `brand-creator site approve --replace` from the round, or put the approved page back"


def _word(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def load_site(project) -> dict:
    """The record of the approved pages, site/site.json of `project`, as read (not validated: validate_site says what is wrong with it). Exit 1 naming the file when it is missing, cannot be read or
    is not a JSON object: the pages are approved by `brand-creator site approve`."""
    f = Path(project) / SITE_FILE
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CliError(EXIT_FAIL, f"{SITE_FILE} is missing: the approved pages are put there by `brand-creator site approve`") from None
    except (OSError, ValueError) as e:
        raise CliError(EXIT_FAIL, f"{SITE_FILE} cannot be read ({type(e).__name__}: {e})") from None
    if not isinstance(doc, dict):
        raise CliError(EXIT_FAIL, f"{SITE_FILE} is not a JSON object")
    return doc


def record_problems(doc, layouts: dict[str, dict] | None = None) -> list[str]:
    """What is wrong with the record itself (without looking at any page file), as sentences ([] when it is sound): schema 1; `approved` and `hero` words; `round` a whole number; at least one page, each with a
    page id (unique), the path site/<id>/index.html, a layout that is an id of page-layouts.json or own:<word>, and a sha256; choices that are each c<number> (unique) with a text, a tag of rule or example, a
    source for every rule, and `pages` (when present) naming only page ids of the record. `layouts` is load_layouts() (read when not given)."""
    if not isinstance(doc, dict):
        return [f"{SITE_FILE} is not a JSON object"]
    known = layouts if layouts is not None else load_layouts()
    problems = []
    missing = [k for k in SITE_KEYS if k not in doc]
    if missing:
        problems.append(f"{SITE_FILE} lacks {', '.join(missing)}")
    if "schema" in doc and doc["schema"] != SCHEMA:
        problems.append(f"schema is {doc['schema']!r}, not {SCHEMA}: this version of brand-creator reads schema {SCHEMA} only")
    if "approved" in doc and not _word(doc["approved"]):
        problems.append("approved is empty: it holds the owner's approval as recorded at G4p")
    if "round" in doc and not (isinstance(doc["round"], int) and not isinstance(doc["round"], bool) and doc["round"] >= 0):
        problems.append(f"round is {doc['round']!r}, not a whole number")
    if "hero" in doc and not _word(doc["hero"]):
        problems.append("hero is empty: it names the hero variant the pages were built from")
    ids: list[str] = []
    pages = doc.get("pages")
    if "pages" in doc:
        if not (isinstance(pages, list) and pages):
            problems.append("pages is not a list with at least one page")
        else:
            for n, page in enumerate(pages, 1):
                if not isinstance(page, dict):
                    problems.append(f"page #{n} is not an object")
                    continue
                pid = page.get("id")
                who = pid if isinstance(pid, str) and pid else f"page #{n}"
                if not (isinstance(pid, str) and SITE_PAGE_ID.fullmatch(pid)):
                    problems.append(f"{who}: the id is not a page id (lowercase letters, digits and -, 2 to 32 characters, starting with a letter)")
                elif pid in ids:
                    problems.append(f"{pid}: the id is used twice")
                else:
                    ids.append(pid)
                    if page.get("path") != f"{SITE_DIR}/{pid}/index.html":
                        problems.append(f"{pid}: the path is {page.get('path')!r}, not {SITE_DIR}/{pid}/index.html")
                layout = page.get("layout")
                if not _word(layout):
                    problems.append(f"{who}: the layout is missing (an id of page-layouts.json, or own:<word>)")
                elif layout not in known and not OWN_LAYOUT.fullmatch(layout):
                    problems.append(f"{who}: the layout {layout!r} is no id of page-layouts.json ({', '.join(known)}) and no own:<word>")
                if not (isinstance(page.get("sha256"), str) and SHA256.fullmatch(page["sha256"])):
                    problems.append(f"{who}: sha256 is not a lowercase hex sha256")
    choices = doc.get("choices")
    if "choices" in doc:
        if not isinstance(choices, list):
            problems.append("choices is not a list")
        else:
            seen: list[str] = []
            for n, c in enumerate(choices, 1):
                if not isinstance(c, dict):
                    problems.append(f"choice #{n} is not an object")
                    continue
                cid = c.get("id")
                who = cid if isinstance(cid, str) and cid else f"choice #{n}"
                if not (isinstance(cid, str) and CHOICE_ID.fullmatch(cid)):
                    problems.append(f"{who}: the id is not c and a number")
                elif cid in seen:
                    problems.append(f"{cid}: the id is used twice")
                else:
                    seen.append(cid)
                if not _word(c.get("text")):
                    problems.append(f"{who}: the choice has no text")
                tag = c.get("tag")
                if tag not in TAGS:
                    problems.append(f"{who}: the tag is {tag!r}, not rule or example")
                elif tag == "rule" and not _word(c.get("source")):
                    problems.append(f"{who}: a rule says where it was decided (source is empty): record the owner's decision in DECISIONS.md, then cite it")
                if "source" in c and not isinstance(c["source"], str):
                    problems.append(f"{who}: source is not text")
                if "pages" in c:
                    named = c["pages"]
                    if not (isinstance(named, list) and named and all(isinstance(x, str) for x in named)):
                        problems.append(f"{who}: pages is not a list of page ids")
                    elif [x for x in named if x not in ids]:
                        problems.append(f"{who}: pages names {', '.join(x for x in named if x not in ids)}, which {'is' if len([x for x in named if x not in ids]) == 1 else 'are'} no page of the record")
    return problems


def file_problems(doc: dict, project) -> list[str]:
    """What is wrong with the pages the record lists, as sentences ([] when each is as approved): every page file is there, and its sha256 is the one the record holds. A page that no longer matches was edited
    after it was approved (scripts/CONTRACT.md "site/site.json"). Pages the record cannot name (a bad id or path) are record_problems' to say."""
    problems = []
    for page in doc.get("pages", []) if isinstance(doc.get("pages"), list) else []:
        if not (isinstance(page, dict) and isinstance(page.get("id"), str) and page.get("path") == f"{SITE_DIR}/{page['id']}/index.html"):
            continue
        f = Path(project) / page["path"]
        if not f.is_file():
            problems.append(f"{page['path']} is missing: {RUN_AGAIN}")
        elif isinstance(page.get("sha256"), str) and SHA256.fullmatch(page["sha256"]) and sha256_file(f) != page["sha256"]:
            problems.append(f"{page['path']} changed since it was approved (its sha256 is not the one in {SITE_FILE}): {RUN_AGAIN}")
    return problems


def validate_site(project) -> list[str]:
    """What is wrong with the approved pages of `project`, as sentences ([] when they are as approved): site/site.json is there and readable, the record is sound (record_problems), and each page file is there
    with the sha256 the record holds (file_problems). The one reading `check` and the book share. Exit 3 only for a damaged plugin install (the layout file)."""
    f = Path(project) / SITE_FILE
    if not f.is_file():
        return [f"{SITE_FILE} is missing: the approved pages are put there by `brand-creator site approve`"]
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"{SITE_FILE} cannot be read ({type(e).__name__}: {e})"]
    problems = record_problems(doc)
    return problems + (file_problems(doc, project) if isinstance(doc, dict) else [])


# ---------------------------------------------------------------- paths that stay true when a page moves

class UrlProblem(NamedTuple):
    code: int       # EXIT_FAIL: the page cannot go (a network address, a root-relative path, a file that is not there); EXIT_USAGE: a path that leaves the project
    message: str


KEEP_SCHEMES = ("data", "mailto", "tel")
NETWORK_SCHEMES = ("http", "https", "ftp", "ftps", "ws", "wss")
_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):")
_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_CSS_URL = re.compile(r"""url\(\s*(?:"(?P<d>[^"]*)"|'(?P<s>[^']*)'|(?P<u>[^)"'\s][^)"']*?))\s*\)|@import\s+(?:"(?P<id>[^"]*)"|'(?P<is>[^']*)')""", re.I)
_TAG = re.compile(r"""<!--.*?-->|<(?P<slash>/)?(?P<name>[A-Za-z][^\s/>"'=]*)(?P<attrs>(?:"[^"]*"|'[^']*'|[^'">])*)>""", re.S)
_ATTR = re.compile(r"""(?P<name>[^\s"'<>/=]+)(?:\s*=\s*(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<uq>[^\s"'=<>`]+)))?""")
_URL_ATTRS = ("src", "href", "poster", "xlink:href")   # a URL each ("data" counts on an <object> only)
_SET_ATTRS = ("srcset", "imagesrcset")                  # a list of URLs, each with a descriptor
_PLAIN_URL = "~!$&'()*+,;=:@"                           # what stays as written when a path is percent-encoded again


def _css_spans(css: str) -> Iterator[tuple[int, int]]:
    """The (start, end) of each URL in a piece of CSS: url(...) in any of its three forms, and @import "...". A comment is not read."""
    comments = [m.span() for m in _COMMENT.finditer(css)]
    for m in _CSS_URL.finditer(css):
        if any(a <= m.start() < b for a, b in comments):
            continue
        for g in ("d", "s", "u", "id", "is"):
            if m.group(g) is not None:
                yield m.start(g), m.end(g)


def _srcset_spans(value: str) -> Iterator[tuple[int, int]]:
    """The (start, end) of each URL in an srcset, as HTML reads one: a URL is a run without white space (a data: URI keeps its comma), whatever follows it up to the next comma outside brackets is its descriptor."""
    i, n = 0, len(value)
    while i < n:
        while i < n and (value[i].isspace() or value[i] == ","):
            i += 1
        j = i
        while j < n and not value[j].isspace():
            j += 1
        if j == i:
            break
        if value[i:j].endswith(","):
            yield i, i + len(value[i:j].rstrip(","))
            i = j
            continue
        yield i, j
        depth = 0
        while j < n:
            ch = value[j]
            j += 1
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                break
        i = j


def _html_spans(text: str) -> Iterator[tuple[int, int]]:
    """The (start, end) of each URL in an HTML text, in the order they are written: src, href, poster and xlink:href, `data` of an <object>, the URLs of srcset and imagesrcset, and the url() and @import of a style
    attribute and of a <style> element. A comment and the text of a <script> are not read; neither are `action`, `content` and the like (they load nothing)."""
    pos = 0
    while True:
        m = _TAG.search(text, pos)
        if m is None:
            return
        pos = m.end()
        if m.group("name") is None or m.group("slash"):
            continue
        tag = m.group("name").lower()
        base = m.start("attrs")
        for a in _ATTR.finditer(m.group("attrs")):
            name = a.group("name").lower()
            g = next((x for x in ("dq", "sq", "uq") if a.group(x) is not None), None)
            if g is None:
                continue
            start = base + a.start(g)
            value = a.group(g)
            if name in _URL_ATTRS or (name == "data" and tag == "object"):
                yield start, start + len(value)
            elif name in _SET_ATTRS:
                for s, e in _srcset_spans(value):
                    yield start + s, start + e
            elif name == "style":
                for s, e in _css_spans(value):
                    yield start + s, start + e
        if tag in ("style", "script"):
            close = re.compile(rf"</{tag}\b", re.I).search(text, pos)
            end = close.start() if close else len(text)
            if tag == "style":
                for s, e in _css_spans(text[pos:end]):
                    yield pos + s, pos + e
            pos = end


def _owner(path: str, moves: dict[str, str]) -> str | None:
    """The folder of `moves` that holds `path` (the longest), or None."""
    found = [k for k in moves if path == k or path.startswith(k + "/")]
    return max(found, key=len) if found else None


def _shown(url: str, limit: int = 80) -> str:
    return url if len(url) <= limit else url[:limit - 3] + "..."


def _decide(url: str, project: Path, file_dir: str, new_file_dir: str, moves: dict[str, str]) -> tuple[str | None, UrlProblem | None]:
    """-> (the URL as it must be written in the new place, or None to leave it as written; the problem that stops the page, or None) for one URL of a file that moves from `file_dir` to `new_file_dir`."""
    s = url.strip()
    if not s or s.startswith("#"):
        return None, None
    scheme = _SCHEME.match(s)
    if s.startswith("//") or (scheme and scheme.group(1).lower() in NETWORK_SCHEMES):
        return None, UrlProblem(EXIT_FAIL, f"{_shown(s)} is an address on the network: a reference page needs no network (use a file of the project, or a # placeholder)")
    if scheme:
        if scheme.group(1).lower() in KEEP_SCHEMES:
            return None, None
        return None, UrlProblem(EXIT_FAIL, f"{_shown(s)} uses the {scheme.group(1).lower()}: scheme, which a reference page cannot rely on (data:, mailto: and tel: are kept)")
    if s.startswith("/"):
        return None, UrlProblem(EXIT_FAIL, f"{_shown(s)} starts with / and leads to a place on a web server, not to a file of the project: write the path relative to the page")
    path_part = re.split(r"[?#]", s, maxsplit=1)[0]
    suffix = s[len(path_part):]
    if not path_part:
        return None, None
    decoded = unquote(path_part)
    resolved = posixpath.normpath(posixpath.join(file_dir, decoded))
    if resolved == ".." or resolved.startswith("../"):
        return None, UrlProblem(EXIT_USAGE, f"{_shown(s)} leads outside the project")
    target = project / resolved
    if not target.exists():
        return None, UrlProblem(EXIT_FAIL, f"{_shown(s)} leads to {resolved}, which does not exist")
    root, real = os.path.realpath(project), os.path.realpath(target)
    if real != root and not real.startswith(root + os.sep):
        return None, UrlProblem(EXIT_USAGE, f"{_shown(s)} leads to {resolved}, which is a link to a place outside the project")
    mine, theirs = _owner(file_dir, moves), _owner(resolved, moves)
    if mine is not None and mine == theirs:
        return None, None   # inside the folder that moves: it moves with the file
    moved = moves[theirs] + resolved[len(theirs):] if theirs is not None else resolved
    new = posixpath.relpath(moved, new_file_dir or ".")
    if decoded.endswith("/") and not new.endswith("/"):
        new += "/"
    if "%" in path_part:
        new = quote(new, safe="/" + _PLAIN_URL)
    if new == path_part:
        return None, None
    return new + suffix, None


def rewrite_urls(text: str, kind: str, *, project, file_dir: str, new_file_dir: str, moves: dict[str, str] | None = None, label: str = "") -> tuple[str, list[UrlProblem]]:
    """The text of an .html (`kind` "html") or .css (`kind` "css") file with the paths in it kept true when the file moves from the project folder `file_dir` to `new_file_dir`
    (both project-relative, posix) -> (the new text, the problems). `moves` maps the folders that move with it (a page's source folder to where it goes: {"rounds/r3/start": "site/start", ...}):
    a path inside the folder the file is in stays as written, a path into another folder of `moves` leads to where that folder goes (a page that links a sibling page keeps a working link),
    and any other path to a file of the project is written again so that it leads to the same file from the new place. The paths read are src, href, poster, xlink:href, srcset (every URL in it) and the
    `data` of an <object>, and url() and @import in a <style> element, a style attribute and a .css file. `#...`, data:, mailto: and tel: stay. A problem stops the page: an http(s) or // address and any
    other scheme, a path starting with /, and a file that is not there are EXIT_FAIL; a path that leaves the project (or a link that leads out of it) is EXIT_USAGE. `label` and the line number begin each
    message. The text of a <script>, a comment, a form's `action` and a URL built by a script are not read: the tool cannot see where they lead."""
    root = Path(project)
    moves = moves or {}
    spans = sorted(_html_spans(text) if kind == "html" else _css_spans(text))
    edits: list[tuple[int, int, str]] = []
    problems: list[UrlProblem] = []
    for start, end in spans:
        url = text[start:end]
        new, problem = _decide(url, root, file_dir, new_file_dir, moves)
        if problem is not None:
            where = f"{label} line {text.count(chr(10), 0, start) + 1}" if label else f"line {text.count(chr(10), 0, start) + 1}"
            problems.append(UrlProblem(problem.code, f"{where}: {problem.message}"))
        elif new is not None:
            lead = url[:len(url) - len(url.lstrip())]
            edits.append((start, end, lead + new + url[len(url.rstrip()):]))
    out = text
    for start, end, new in reversed(edits):
        out = out[:start] + new + out[end:]
    return out, problems
