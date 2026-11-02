"""Wiring: what a site's source is tied to, read as text. Standard library only.

A redesign can drop a link, a form field name, a handler, a test hook, an id or a script that the product, its tests or its analytics depend on.
`brand-creator adoption wiring` records those items before and after (docs/adr/ADR-0012). This module is the reading: text in, items out. It
chooses no file and writes nothing; `adoption.py` lists the files and stores the record.

An item is `kind:value`, with everything after the colon cut at 120 characters. The six kinds:

  link     the value of href, to, action, formAction (formaction too); an empty value and `#` are skipped, and so is href on link, script,
           base, use, image and style (they load a file, they are not a way to move)
  field    name="..." on any tag but meta, link, a, iframe, param, slot, map and object; and the string argument of register("...")
  handler  an attribute that has a value and is an event name of the one list (scripts/data/event-handlers.json: `onclick`, `onsubmit` ...; `onboarding`,
           `one` and `only` only start with "on" and are not), a component prop `on[A-Z]...` (`onClick`), `@event`, `v-on:event` or `on:event`:
           `handler:<attribute>=<value>`. The page side (pagelib/wiring.mjs) reads the same list, so the two sides agree on the names the DOM can show
  hook     data-testid, data-test, data-cy, data-qa and data-track*, data-analytics*, data-event*, data-gtm*: `hook:<attribute>=<value>`
  id       a static id="..." (no braces, no white space)
  script   the src of a <script>, without its query and without a leading ./

A value is a quoted string or a `{...}` expression kept with its braces, balanced to three levels, with its white space squashed. HTML comments
are removed first, and the body of a <script> or <style> is not read as markup. The reading is by pattern, so it is approximate: a value built
at run time, a deeper expression or a tag a template engine assembles is missed or noisy (ADR-0012, Consequences).

A page of the owner's own local server is read too (`adoption wiring --page URL`): `render.mjs wiring` prints the same six kinds from the rendered DOM
(scripts/pagelib/wiring.mjs) and `rendered_items` turns that into the same `kind:value` items, so an item found in both places is one item. The file it is
recorded under is `rendered:<path of the URL>` (`rendered_source`).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

EXTENSIONS = (".html", ".htm", ".jsx", ".tsx", ".js", ".ts", ".mjs", ".vue", ".svelte", ".astro", ".erb", ".ejs", ".hbs", ".handlebars",
              ".njk", ".liquid", ".twig", ".php", ".mdx")
KINDS = ("link", "field", "handler", "hook", "id", "script")
MAX_VALUE = 120      # characters of an item after `kind:`
MAX_FILES = 5        # files kept for an item
NEST = 3             # levels of braces a `{...}` value may nest
SPAN = 50000         # characters a single tag is followed for: a `<` that is no tag stops being read here

LINK_ATTRS = {"href", "to", "action", "formAction", "formaction"}
LINK_NOT_ON = {"link", "script", "base", "use", "image", "style"}
FIELD_NOT_ON = {"meta", "link", "a", "iframe", "param", "slot", "map", "object"}
EVENTS_FILE = Path(__file__).resolve().parent.parent / "data" / "event-handlers.json"
EVENT_HANDLERS = frozenset(json.loads(EVENTS_FILE.read_text(encoding="utf-8"))["events"])   # the one list of event-handler attribute names; pagelib/wiring.mjs reads the same file

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_RAW = re.compile(r"(<(script|style)\b[^>]*>)(.*?)(</\2\s*>)", re.S | re.I)
_TAG = re.compile(r"<([A-Za-z][\w:.\-]*)")
_NAME = re.compile(r"[^\s=<>\"'{}/]+")
_LOOSE = re.compile(r"[^\s>]*")
_BRACE = re.compile(r"[{}]")
_HANDLER = re.compile(r"on[A-Z]\w*|@[^\s]+|v-on:[^\s]+|on:[^\s]+")   # the forms the DOM never shows; a plain lowercase name (onclick) is a handler only when EVENT_HANDLERS has it
_HOOK = re.compile(r"data-(?:testid|test|cy|qa)|data-(?:track|analytics|event|gtm)[\w\-]*")
_REGISTER = re.compile(r"(?<![\w$])register\(\s*(?P<q>[\"'`])(?P<v>[^\"'`\n]+?)(?P=q)")
_SPACE = re.compile(r"\s+")


def is_source(path: str) -> bool:
    """Whether the file is read for wiring (by its extension)."""
    return path.lower().endswith(EXTENSIONS)


def squash(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


def _braces(text: str, i: int, end: int) -> tuple[int, bool] | None:
    """text[i] is `{`: (the index after its matching `}`, whether it stays within NEST levels), or None when it never closes."""
    depth = deepest = 0
    for m in _BRACE.finditer(text, i, end):
        if m.group() == "{":
            depth += 1
            deepest = max(deepest, depth)
        else:
            depth -= 1
            if depth == 0:
                return m.end(), deepest <= NEST
    return None


def _attributes(text: str, i: int):
    """The attributes of the tag whose name ended at `i`: (name, value, braced) with value None for a `{...}` nested deeper than NEST levels.
    Stops at the tag's `>`, at a `<` that opens something else, and where a quote or a brace never closes."""
    end = min(len(text), i + SPAN)
    while i < end:
        c = text[i]
        if c.isspace() or c == "/":
            i += 1
        elif c == ">":
            return
        elif c == "<":
            close = {"<%": "%>", "<?": "?>"}.get(text[i:i + 2])
            if close is None:
                return
            j = text.find(close, i + 2, end)
            if j < 0:
                return
            i = j + 2
        elif c == "{":
            got = _braces(text, i, end)
            if got is None:
                return
            i = got[0]
        elif c in "\"'":
            j = text.find(c, i + 1, end)
            if j < 0:
                return
            i = j + 1
        else:
            name = _NAME.match(text, i)
            if name is None:
                i += 1
                continue
            i = name.end()
            j = i
            while j < end and text[j].isspace():
                j += 1
            if j >= end or text[j] != "=":
                continue
            j += 1
            while j < end and text[j].isspace():
                j += 1
            if j >= end:
                return
            q = text[j]
            if q in "\"'":
                k = text.find(q, j + 1, end)
                if k < 0:
                    return
                yield name.group(), text[j + 1:k], False
                i = k + 1
            elif q == "{":
                got = _braces(text, j, end)
                if got is None:
                    return
                yield name.group(), (text[j:got[0]] if got[1] else None), True
                i = got[0]
            else:
                i = _LOOSE.match(text, j).end()    # an unquoted value is not read


def _kind(tag: str, name: str) -> str | None:
    if name in LINK_ATTRS and tag not in LINK_NOT_ON:
        return "link"
    if name == "name" and tag not in FIELD_NOT_ON:
        return "field"
    if name in EVENT_HANDLERS or _HANDLER.fullmatch(name):
        return "handler"
    if _HOOK.fullmatch(name):
        return "hook"
    if name == "id":
        return "id"
    if name == "src" and tag == "script":
        return "script"
    return None


def _item(kind: str, name: str, value: str, braced: bool) -> str | None:
    v = squash(value)
    if kind == "link":
        text = None if v in ("", "#") else v
    elif kind in ("field", "handler", "hook"):
        text = None if v in ("", "{}") else (v if kind == "field" else f"{name}={v}")
    elif kind == "id":
        text = None if braced or not v or re.search(r"[{}\s]", v) else v
    else:    # script
        v = v if braced else v.split("?", 1)[0].removeprefix("./")
        text = v or None
    return None if text is None else f"{kind}:{text[:MAX_VALUE]}"


def scan_text(text: str) -> tuple[list[str], int]:
    """(the items of one file in the order they were met, without repeats; how many wiring values were nested deeper than NEST levels and so not read)."""
    text = _COMMENT.sub(" ", text)
    items: dict[str, None] = {}
    deep = 0
    markup = _RAW.sub(lambda m: m.group(1) + " " + m.group(4), text)
    for tag in _TAG.finditer(markup):
        for name, value, braced in _attributes(markup, tag.end()):
            kind = _kind(tag.group(1), name)
            if kind is None:
                continue
            if value is None:
                deep += 1
                continue
            item = _item(kind, name, value, braced)
            if item is not None:
                items[item] = None
    for m in _REGISTER.finditer(text):
        s = m.start()
        if text[s - 1:s] == "." and text[s - 3:s] != "...":    # x.register("..."): a method of something else; {...register("...")} is the form library
            continue
        v = squash(m.group("v"))
        if v:
            items[f"field:{v[:MAX_VALUE]}"] = None
    return list(items), deep


def rendered_source(url: str) -> str:
    """The file label of an item read from a rendered page: `rendered:<path of the URL>`. Only the path, so the page keeps its label when the dev server
    comes up on another port."""
    return "rendered:" + (urlsplit(url).path or "/")


def rendered_items(data: object) -> list[str]:
    """The items of one rendered page from what `render.mjs wiring` printed, `{kind: [value, ...]}` for exactly the six kinds, in document order, without repeats.
    White space is squashed and everything after `kind:` is cut at MAX_VALUE characters again (the browser side does the same). ValueError for any other shape."""
    if not isinstance(data, dict) or set(data) != set(KINDS):
        raise ValueError("expected an object with the keys " + ", ".join(KINDS))
    items: dict[str, None] = {}
    for kind in KINDS:
        values = data[kind]
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError(f"{kind} is not a list of strings")
        for v in values:
            text = squash(v)
            if text:
                items[f"{kind}:{text[:MAX_VALUE]}"] = None
    return list(items)


def add(store: dict[str, list[str]], path: str, items: list[str]) -> None:
    """Remember that `path` holds each item; an item keeps its first MAX_FILES files."""
    for it in items:
        files = store.setdefault(it, [])
        if len(files) < MAX_FILES and path not in files:
            files.append(path)


def kind_counts(items) -> dict[str, int]:
    """Items per kind, in the order of KINDS."""
    n = {k: 0 for k in KINDS}
    for it in items:
        k = it.split(":", 1)[0]
        if k in n:
            n[k] += 1
    return n
