"""The brand book lint: every rule, as a function of the book text and the project's data. Standard library only.

Used by book_lint.py (the gate), book.py (a book that does not lint is not written), book_pdf.py and check. Each rule is one
result row {id, status, label, detail}; status is pass, fail, warn, info or skipped. See scripts/CONTRACT.md, "Brand book".
"""
from __future__ import annotations

import base64
import fnmatch
import html as _html
import re
import urllib.parse
from pathlib import Path

import bookdata
import htmlscan
from _color import parse_hex
from mark_lint import lint_svg_text

SHAPE_TAGS = {"h2", "h3", "h4", "p", "li", "tr", "figure", "blockquote", "pre", "img"}
PROSE_DROP = re.compile(r"<(table|svg|style|script|code|pre)\b.*?</\1\s*>", re.I | re.S)
NAMED_COLOURS = set("""aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood cadetblue
chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki
darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise
darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod
gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue
lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue
lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid
mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin
navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip
peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna
silver skyblue slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke
yellow yellowgreen""".split())
COLOUR_OK = {"transparent", "currentcolor", "inherit", "initial", "unset", "none", "revert", "auto", "normal"}
FONT_KEYWORDS = {"xx-small": 9, "x-small": 10, "small": 13, "medium": 16, "large": 18, "x-large": 24, "xx-large": 32, "larger": 18}


def row(id: str, status: str, label: str, detail: str = "", **extra) -> dict:
    return {"id": id, "status": status, "label": label, "detail": detail, **extra}


def _ctx(text: str, m: re.Match, width: int = 50) -> str:
    a, b = max(0, m.start() - width), min(len(text), m.end() + width)
    return ("..." if a else "") + text[a:b].replace("\n", " ") + ("..." if b < len(text) else "")


def _data_uri_text(src: str) -> str | None:
    """Decoded text of a data:image/svg+xml URI, else None."""
    m = re.match(r"(?is)^data:image/svg\+xml(;[^,]*)?,(.*)$", src.strip())
    if not m:
        return None
    try:
        if "base64" in (m.group(1) or ""):
            return base64.b64decode(m.group(2)).decode("utf-8", "replace")
        return urllib.parse.unquote(m.group(2))
    except (ValueError, UnicodeDecodeError):
        return ""


# ---------------------------------------------------------------- CSS reading (for the self-consistency rules)

def css_blocks(css: str) -> list[tuple[str, str]]:
    out, i = [], 0
    while i < len(css):
        j = css.find("{", i)
        if j < 0:
            break
        depth, k = 1, j + 1
        while k < len(css) and depth:
            depth += (css[k] == "{") - (css[k] == "}")
            k += 1
        body = css[j + 1:k - 1]
        if "{" in body:
            out += css_blocks(body)
        else:
            out.append((css[i:j].strip(), body))
        i = k
    return out


def decls(body: str) -> list[tuple[str, str]]:
    out = []
    for part in re.split(r";(?![^()]*\))", body):
        if ":" in part:
            p, v = part.split(":", 1)
            if p.strip():
                out.append((p.strip().lower(), v.strip()))
    return out


def _strip_data(css: str) -> str:
    return re.sub(r"url\(\s*(['\"]?)data:[^)]*\)", "url(data)", css, flags=re.I)


def book_css_decls(text: str) -> list[tuple[str, str, str]]:
    """(where, property, value) of every declaration in <style> elements and style="" attributes."""
    out = []
    for m in re.finditer(r"<style\b[^>]*>(.*?)</style\s*>", text, re.I | re.S):
        css = re.sub(r"/\*.*?\*/", "", _strip_data(m.group(1)), flags=re.S)
        for prelude, body in css_blocks(css):
            for p, v in decls(body):
                out.append((prelude or "style", p, v))
    for t in htmlscan.tags(text):
        if not t.closing:
            st = t.attrs.get("style")
            if st:
                for p, v in decls(_strip_data(st)):
                    out.append((f"<{t.name} style>", p, v))
    return out


def normalise_colour(tok: str) -> str | None:
    tok = tok.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{3,4}", tok):
        return "#" + "".join(c * 2 for c in tok[1:4])
    if re.fullmatch(r"#[0-9a-f]{6}([0-9a-f]{2})?", tok):
        return tok[:7]
    return None


def colours_in(value: str) -> tuple[list[str], list[str]]:
    """-> (colours as #rrggbb, problems) found in one CSS value."""
    cols, bad = [], []
    v = re.sub(r"url\([^)]*\)", " ", value)
    for m in re.finditer(r"#[0-9a-fA-F]{3,8}(?![0-9a-zA-Z_-])", v):
        c = normalise_colour(m.group(0))
        (cols if c else bad).append(c or m.group(0))
    for m in re.finditer(r"\b(rgba?)\(([^)]*)\)", v, re.I):
        nums = re.findall(r"[0-9.]+%?", m.group(2))
        try:
            rgb = [round(float(n[:-1]) * 2.55) if n.endswith("%") else round(float(n)) for n in nums[:3]]
            cols.append("#%02x%02x%02x" % tuple(rgb))
        except (ValueError, TypeError):
            bad.append(m.group(0))
    for m in re.finditer(r"\b(hsla?|hwb|lab|lch|oklab|oklch|color-mix|light-dark|color)\(", v, re.I):
        bad.append(f"{m.group(1)}() (write the token's #rrggbb)")
    stripped = re.sub(r"#[0-9a-fA-F]+|\b\w+\([^)]*\)", " ", v)
    for w in re.findall(r"[A-Za-z]+", stripped):
        if w.lower() in NAMED_COLOURS and w.lower() not in COLOUR_OK:
            bad.append(w)
    return cols, bad


def font_px(value: str, prop: str) -> tuple[float | None, str | None]:
    """-> (px size, problem). Relative units are taken against a 16 px parent; var() cannot be resolved and is a problem."""
    v = value.strip().lower().replace("!important", "").strip()
    if prop == "font":
        if re.search(r"\bvar\(", v):
            return None, "font shorthand uses var(); write the size in px"
        m = re.search(r"(?:^|\s)(\d*\.?\d+)(px|rem|em|pt|%)(?:/\S+)?(?=\s|$)", v)
        if m:
            v = m.group(1) + m.group(2)
        else:
            kw = next((k for k in FONT_KEYWORDS if re.search(rf"(?:^|\s){k}(?:/\S+)?(?=\s|$)", v)), None)
            if kw:
                return float(FONT_KEYWORDS[kw]), None
            return None, None
    if v in ("inherit", "initial", "unset", "revert", "medium"):
        return None, None
    if v in FONT_KEYWORDS:
        return float(FONT_KEYWORDS[v]), None
    if v == "smaller":
        return None, "font-size: smaller is relative to its parent; write px"
    if "var(" in v or "calc(" in v or "clamp(" in v or "min(" in v or "max(" in v:
        return None, f"font-size {value!r} cannot be resolved by the lint; write a plain px value"
    m = re.fullmatch(r"(\d*\.?\d+)(px|rem|em|pt|%)", v)
    if not m:
        return None, f"font-size {value!r} is not a size the lint reads"
    n, u = float(m.group(1)), m.group(2)
    return {"px": n, "rem": n * 16, "em": n * 16, "pt": n * 96 / 72, "%": n * 16 / 100}[u], None


# ---------------------------------------------------------------- the rules

def lint(project: Path, text: str, *, path: str, view: dict, cfg: dict, tokens_doc: dict, facts_rows: list[dict],
         self_consistency: bool = False, allow_variants: bool = False, is_html: bool = True) -> list[dict]:
    L = cfg["lint"]
    res: list[dict] = []
    visible = htmlscan.visible_text(text) if is_html else text

    try:
        els = list(htmlscan.tags(text)) if is_html else []
        if is_html:
            for t in els:
                if not t.closing and not t.void:
                    htmlscan.element_end(text, t)
    except ValueError as e:
        res.append(row("html:structure", "fail", "tags are balanced", str(e)))
        return res

    if is_html:
        res += _head_rules(text)
        res += _id_rules(text)
        res += _network_rules(project, text, L, path)
        res += _marks_rules(project, text, path)
        res += _images_alt(text)
    res += _word_rules(project, text, visible, L, facts_rows, is_html)
    if is_html:
        res += _variant_rules(text, allow_variants)
        res += _chapter_rules(project, text, view)
        res += _edition_rules(text, view, cfg)
        res += _count_rules(project, text, cfg, tokens_doc, facts_rows)
        res += _file_rules(project, text, L)
        res += _legal_rules(visible, facts_rows)
        res += _parity_rules(text, view)
        res += _language_rules(text, view)
        if self_consistency:
            res += _self_rules(text, cfg, tokens_doc)
    return res


def _head_rules(text: str) -> list[dict]:
    probs = []
    if not re.search(r"<html\b[^>]*\blang\s*=\s*[\"'][A-Za-z-]+[\"']", text):
        probs.append("<html> has no lang attribute")
    m = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
    if not m or not m.group(1).strip():
        probs.append("no <title>")
    if not re.search(r"<meta\b[^>]*charset", text, re.I):
        probs.append("no <meta charset>")
    if not re.search(r"<meta\b[^>]*name=[\"']viewport[\"']", text, re.I):
        probs.append("no viewport meta (the 390 px view needs it)")
    if not re.search(r"prefers-color-scheme\s*:\s*dark", text):
        probs.append("no prefers-color-scheme: dark rule (the book must work in light and dark)")
    return [row("html:head", "fail" if probs else "pass", "lang, title, viewport and a dark scheme are present", "; ".join(probs))]


def _id_rules(text: str) -> list[dict]:
    ids = [t.attrs["id"] for t in htmlscan.tags(text) if not t.closing and "id" in t.attrs]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    hrefs = [t.attrs["href"] for t in htmlscan.tags(text) if not t.closing and t.name == "a" and t.attrs.get("href", "").startswith("#")]
    bad = sorted({h for h in hrefs if h[1:] not in ids and h != "#"})
    return [row("ids:duplicate", "fail" if dup else "pass", "ids are unique", f"duplicate ids: {dup}" if dup else f"{len(ids)} ids"),
            row("anchors:broken", "fail" if bad else "pass", "every #anchor has its target", f"links to missing ids: {bad}" if bad else f"{len(hrefs)} anchors")]


def _network_rules(project: Path, text: str, L: dict, path: str) -> list[dict]:
    probs, warns = [], []
    allow = set(L["allow_external_links"])
    for t in htmlscan.tags(text):
        if t.closing:
            continue
        a = t.attrs
        loc = f"line {htmlscan.line_of(text, t.start)}"
        if t.name == "script":
            probs.append(f"<script> element ({loc}); the book has no script")
        if t.name == "base":
            probs.append(f"<base> element ({loc})")
        if t.name == "meta" and a.get("http-equiv", "").lower() == "refresh":
            probs.append(f"meta refresh ({loc})")
        for k in a:
            if k.startswith("on"):
                probs.append(f"event handler {k}= on <{t.name}> ({loc}); the book has no script")
        for k in ("src", "poster", "data", "srcset", "ping"):
            v = a.get(k, "")
            if v and not v.lower().startswith(("data:", "#")):
                first = v.split()[0] if k == "srcset" else v
                if first.lower().startswith(("data:",)):
                    continue
                probs.append(f"<{t.name} {k}={v[:60]!r}> is not embedded ({loc}); inline it as a data: URI")
        if t.name == "link" and a.get("href") and not a["href"].lower().startswith("data:"):
            probs.append(f"<link href={a['href'][:60]!r}> ({loc}); fonts and styles are inline")
        if t.name in ("iframe", "object", "embed", "form"):
            probs.append(f"<{t.name}> element ({loc})")
        if t.name == "a" and a.get("href"):
            h = a["href"].strip()
            if re.match(r"(?i)^(https?:)?//", h):
                if h not in allow:
                    probs.append(f"network address in a link: {h[:70]!r} ({loc}); a book makes no network references")
            elif re.match(r"(?i)^(javascript|data|vbscript):", h):
                probs.append(f"{h[:20]!r} link ({loc})")
            elif not h.startswith(("#", "mailto:")):
                warns.append(h)
    stripped = re.sub(r"url\(\s*(['\"]?)data:[^)]*\)", "url(data)", re.sub(r"<!--.*?-->", "", text, flags=re.S), flags=re.I)
    for m in re.finditer(r"url\(\s*['\"]?\s*(?!data\)|#)([^)'\"]+)", stripped, re.I):
        probs.append(f"CSS url({m.group(1)[:60]}) is not embedded")
    for m in re.finditer(r"@import\b", stripped):
        probs.append("CSS @import")
    for m in re.finditer(r"(?<![\w.-])https?://[^\s\"'<>)]+", re.sub(r"<(svg)\b.*?</\1>", "", stripped, flags=re.S)):
        s = m.group(0)
        if s.rstrip("/.,;") not in allow and not any(s.startswith(a) for a in allow):
            probs.append(f"network address in the text: {s[:70]!r}")
    out = [row("network:refs", "fail" if probs else "pass", "no network address, script or file the book needs at read time",
               "; ".join(sorted(set(probs))[:6]) + (f" (+{len(set(probs)) - 6} more)" if len(set(probs)) > 6 else "") if probs
               else "everything the book shows is inline")]
    if warns:
        out.append(row("links:files", "warn", "links to files outside the book", f"{len(warns)} link(s): {', '.join(sorted(set(warns))[:4])}; they stay links "
                       "and break when the book is moved without them"))
    return out


def _svg_issues(svg: str, *, diagram: bool) -> list[str]:
    probs = lint_svg_text(svg)
    if diagram:   # a labelled diagram may hold text; scripts, foreign objects and external references stay forbidden
        probs = [p for p in probs if not p.startswith(("<text", "<tspan", "font-family", "@font-face"))]
    return probs


def _marks_rules(project: Path, text: str, path: str) -> list[dict]:
    found, probs = 0, []
    base = (project / path).parent if (project / path).parent.is_dir() else project
    for t in htmlscan.tags(text):
        if t.closing:
            continue
        a = t.attrs
        if t.name == "svg":
            end = htmlscan.element_end(text, t)
            found += 1
            name = a.get("data-mark") or a.get("data-diagram") or a.get("aria-label") or "inline svg"
            for p in _svg_issues(text[t.start:end], diagram="data-diagram" in a and "data-mark" not in a):
                probs.append(f"{name}: {p}")
        elif t.name == "img":
            src = a.get("src", "")
            svg = _data_uri_text(src)
            kind = "mark" if "data-mark" in a else "diagram" if "data-diagram" in a else None
            if svg is not None:
                if kind:
                    found += 1
                    for p in _svg_issues(svg, diagram=kind == "diagram"):
                        probs.append(f"{a.get('data-mark') or a.get('data-diagram')}: {p}")
            elif src.lower().endswith(".svg") and not re.match(r"(?i)^(https?:)?//", src):
                f = (base / src).resolve()
                try:
                    f.relative_to(project.resolve())
                except ValueError:
                    probs.append(f"{src}: a mark file outside the project")
                    continue
                if f.is_file():
                    found += 1
                    for p in _svg_issues(f.read_text(encoding="utf-8", errors="replace"), diagram="data-diagram" in a):
                        probs.append(f"{src}: {p}")
    if probs:
        return [row("marks:lint", "fail", "every embedded mark is pure vector (no <text>, fonts or external references)",
                    "; ".join(sorted(set(probs))[:6]))]
    if not found:
        return [row("marks:lint", "warn", "an embedded mark was found to lint", "no <svg>, mark image or linked .svg in the book")]
    return [row("marks:lint", "pass", "every embedded mark is pure vector (no <text>, fonts or external references)", f"{found} drawing(s) checked")]


def _images_alt(text: str) -> list[dict]:
    bad = [htmlscan.line_of(text, t.start) for t in htmlscan.tags(text) if not t.closing and t.name == "img" and "alt" not in t.attrs]
    return [row("images:alt", "fail" if bad else "pass", "every image has an alt attribute", f"no alt on line(s) {bad[:6]}" if bad else "")]


def _history_cut(text: str, chapter: str) -> tuple[str, str]:
    """-> (text without the history chapter, the history chapter's own text)."""
    for t in htmlscan.tags(text):
        if not t.closing and t.name == "section" and t.attrs.get("data-chapter") == chapter:
            end = htmlscan.element_end(text, t)
            return text[:t.start] + " " + text[end:], text[t.start:end]
    return text, ""


def _word_rules(project: Path, text: str, visible: str, L: dict, facts_rows: list[dict], is_html: bool) -> list[dict]:
    from _common import forbidden_terms
    out = []
    outside, _hist = _history_cut(text, L["history_chapter"]) if is_html else (text, "")
    outside_vis = htmlscan.visible_text(outside) if is_html else text

    def scan(patterns, hay, flags=0):
        hits = []
        for p in patterns:
            for m in re.finditer(p, hay, flags):
                hits.append(f"{m.group(0)!r} in \"{_ctx(hay, m)}\"")
        return hits

    sc = scan(L["scratch"], visible if not is_html else htmlscan.visible_text(text), re.I)
    out.append(row("words:scratch", "fail" if sc else "pass", "no scratch or placeholder words", "; ".join(sc[:4]) if sc else ""))
    rd = scan(L["round"], outside_vis)
    out.append(row("words:round", "fail" if rd else "pass",
                   f"no round, version, item or decision language outside the {L['history_chapter']} chapter",
                   "; ".join(rd[:4]) if rd else ""))
    terms = list(dict.fromkeys(forbidden_terms(project) + L["forbidden"]))
    fb = []
    for term in terms:
        for m in re.finditer(r"(?<!\w)" + re.escape(term) + r"(?!\w)", outside_vis, re.I):
            fb.append(f"{term!r} in \"{_ctx(outside_vis, m)}\"")
    out.append(row("words:forbidden", "fail" if fb else "pass", "none of the project's FORBIDDEN words",
                   "; ".join(fb[:4]) if fb else f"{len(terms)} word(s) checked"))
    backing = " \n".join(r.get("value", "").lower() for r in facts_rows)
    unbacked = []
    for w in L["status_words"]:
        for m in re.finditer(r"(?<!\w)" + re.escape(w) + r"(?!\w)", visible, re.I):
            if w.lower() not in backing:
                unbacked.append(f"{w!r} in \"{_ctx(visible, m)}\"")
    out.append(row("words:status", "fail" if unbacked else "pass", "every status word is backed by a FACTS.md value",
                   ("; ".join(unbacked[:4]) + "; add the fact to FACTS.md (owner-confirmed) or remove the claim") if unbacked else ""))
    return out


def _variant_rules(text: str, allow: bool) -> list[dict]:
    hits = [f"{t.attrs.get('data-variant') or t.attrs.get('data-switcher')} (line {htmlscan.line_of(text, t.start)})"
            for t in htmlscan.tags(text) if not t.closing and ("data-variant" in t.attrs or "data-switcher" in t.attrs)]
    words = [m.group(0) for m in re.finditer(r"\bVariant [A-Z]\b|\b[Ss]witcher\b", htmlscan.visible_text(text))]
    if hits or words:
        detail = f"{len(hits)} open choice block(s): {', '.join(hits[:4])}" + (f"; words {sorted(set(words))}" if words else "")
        detail += "; run `brand-creator collapse` after the decision"
        return [row("variants:open", "warn" if allow else "fail", "no losing variant or switcher is left in the book", detail)]
    return [row("variants:open", "pass", "no losing variant or switcher is left in the book")]


def _chapter_rules(project: Path, text: str, view: dict) -> list[dict]:
    need = bookdata.chapters_for(project, view)
    have = [t.attrs["data-chapter"] for t in htmlscan.tags(text) if not t.closing and t.name == "section" and "data-chapter" in t.attrs]
    missing = [c for c in need if c not in have]
    return [row("chapters:required", "fail" if missing else "pass", f"the chapters a {view['tier']} book needs are present",
                f"missing: {', '.join(missing)} (needed for tier {view['tier']}, architecture {view['architecture']})" if missing
                else f"{len(need)} required chapter(s) present")]


def _edition_rules(text: str, view: dict, cfg: dict) -> list[dict]:
    cover = next((t for t in htmlscan.tags(text) if not t.closing and "data-cover" in t.attrs), None)
    if cover is None:
        return [row("edition:stamp", "fail", "the cover carries the edition and the approval stamp from BRAND-STATE.md",
                    "no element with data-cover (the cover section)")]
    a = cover.attrs
    state, date = bookdata.approval(view)
    probs = []
    if a.get("data-edition") != str(view["edition"]):
        probs.append(f"cover edition is {a.get('data-edition')!r}, BRAND-STATE.md says {view['edition']}")
    if a.get("data-stamp") != state:
        probs.append(f"cover stamp is {a.get('data-stamp')!r}; BRAND-STATE.md gates say {state} "
                     f"(G5 {'recorded' if view['g5'] else 'not recorded'}, approved_edition {view['approved_edition']}, edition {view['edition']})")
    end = htmlscan.element_end(text, cover)
    cover_text = htmlscan.visible_text(text[cover.start:end], with_attributes=False)
    lang = view["content_languages"][0]
    word = bookdata.stamp_word(cfg, lang)   # the first content language's label for APPROVED, else APPROVED
    mark = next((t for t in htmlscan.tags(text[cover.start:end]) if not t.closing and "data-stamp-text" in t.attrs), None)   # the stamp element
    seen = htmlscan.visible_text(text[cover.start:end][mark.start:htmlscan.element_end(text[cover.start:end], mark)], with_attributes=False) if mark else cover_text
    stamped = bool(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", seen))   # in the stamp, so a cover label that shares the word cannot pass for it
    if stamped != (state == "approved"):
        probs.append("the cover text " + (f"says {word} but the edition is not approved" if stamped else f"has no {word} stamp but the edition is approved"
                                          + (f" (the first content language is {lang}: its stamp word is the labels.{lang}.APPROVED of book/book.json)" if word != bookdata.APPROVED else "")))
    if state == "approved" and date and date not in cover_text:
        probs.append(f"the cover does not show the approval date {date}")
    if probs:
        probs.append("a generated book follows BRAND-STATE.md when rebuilt (`brand-creator book`); a hand-authored book is patched: change the cover's "
                     f"data-edition, data-stamp and {word} <date> text with `brand-creator patch`, and do that before recording G5")
    return [row("edition:stamp", "fail" if probs else "pass", "the cover carries the edition and the approval stamp from BRAND-STATE.md",
                "; ".join(probs) if probs else f"edition {view['edition']}, {state}" + (f" {date}" if date else ""))]


def _count_rules(project: Path, text: str, cfg: dict, doc: dict, facts_rows: list[dict]) -> list[dict]:
    chapters = sum(1 for t in htmlscan.tags(text) if not t.closing and t.name == "section" and "data-chapter" in t.attrs)
    want = bookdata.counts(project, cfg, doc, chapters)
    probs = []
    n = 0
    for t in htmlscan.tags(text):
        if t.closing:
            continue
        if "data-count" in t.attrs:
            n += 1
            name = t.attrs["data-count"]
            end = htmlscan.element_end(text, t)
            shown = htmlscan.visible_text(text[t.start:end], with_attributes=False).strip()
            if name not in want:
                probs.append(f"data-count={name!r} is not a count the book knows ({', '.join(bookdata.COUNT_NAMES)})")
            elif shown != str(want[name]):
                probs.append(f"{name}: the book says {shown}, the data say {want[name]}")
    out = [row("counts:data", "fail" if probs else "pass", "every computed count equals the data", "; ".join(probs[:5]) if probs else f"{n} count(s)")]
    prose = htmlscan.visible_text(PROSE_DROP.sub(" ", re.sub(r"<span\b[^>]*data-count[^>]*>.*?</span>", " ", text, flags=re.S)))
    typed = []
    for key, nouns in cfg["lint"]["count_nouns"].items():
        if key not in want:
            continue
        alt = "|".join(re.escape(x) for x in sorted(nouns, key=len, reverse=True))
        for m in re.finditer(rf"(?<![\w.,/:#-])(\d[\d,]*)\s+({alt})(?![\w-])", prose, re.I):
            val = int(m.group(1).replace(",", ""))
            if val != want[key]:
                typed.append(f"\"{m.group(0)}\" but the data say {want[key]} {key}")
    out.append(row("counts:typed", "fail" if typed else "pass", "a number typed in prose agrees with the data (use {{count:name}} so it cannot drift)",
                   ("; ".join(typed[:4]) + "; write it as {{count:NAME}}") if typed else ""))
    fprobs = []
    for t in htmlscan.tags(text):
        if not t.closing and "data-fact" in t.attrs:
            label = t.attrs["data-fact"]
            end = htmlscan.element_end(text, t)
            shown = htmlscan.visible_text(text[t.start:end], with_attributes=False).strip()
            v = bookdata.fact_value(facts_rows, label)
            if v is None:
                fprobs.append(f"FACTS.md has no row {label!r}")
            elif " ".join(v.split()) != shown:
                fprobs.append(f"{label}: the book says {shown!r}, FACTS.md says {v!r}")
    out.append(row("facts:data", "fail" if fprobs else "pass", "every quoted fact equals its FACTS.md value", "; ".join(fprobs[:4])))
    return out


def book_file_rows(project: Path) -> dict[str, str]:
    """{path: sha8} the files table must account for: every manifest row and every source artwork file."""
    rows = {r["path"]: r["sha256"][:8] for r in bookdata.manifest_rows(project)}
    for f in bookdata.logo_files(project):
        rows.setdefault(f.relative_to(project).as_posix(), bookdata.sha8(f.read_bytes()))
    return rows


def _file_rules(project: Path, text: str, L: dict) -> list[dict]:
    want = book_file_rows(project)
    for pat in L["files_exclude"]:
        for p in [p for p in want if fnmatch.fnmatch(p, pat)]:
            del want[p]
    got: dict[str, str] = {}
    for t in htmlscan.tags(text):
        if not t.closing and "data-path" in t.attrs:
            got[t.attrs["data-path"]] = t.attrs.get("data-sha", "")
    probs = []
    missing = sorted(set(want) - set(got))
    if missing:
        probs.append(f"{len(missing)} file(s) are not accounted for in the files chapter: {', '.join(missing[:4])}")
    for p, s in sorted(got.items()):
        f = project / p
        if not f.is_file():
            probs.append(f"the book lists {p}, which does not exist")
        elif p in want and s and s != want[p]:
            probs.append(f"{p}: the book has sha {s}, the file is {want[p]} (rebuild the book)")
    return [row("files:accounting", "fail" if probs else "pass", "the files chapter accounts for every manifest row and source artwork file",
                "; ".join(probs[:4]) if probs else f"{len(got)} file row(s), {len(want)} required")]


def _legal_rules(visible: str, facts_rows: list[dict]) -> list[dict]:
    legal = [r for r in facts_rows if r.get("fact", "").lower().startswith("legal")]
    flat = " ".join(visible.split()).casefold()
    out = []
    for r in legal:
        v = " ".join(r.get("value", "").split())
        ok = bool(v) and v.casefold() in flat
        out.append(row(f"legal:{r['fact']}", "pass" if ok else "fail", "a required legal disclosure from FACTS.md appears verbatim",
                       f"{r['fact']}: " + ("shown" if ok else f"{v!r} is not in the book")))
    return out


LANG_DIR = Path(__file__).resolve().parent.parent / "data" / "languages"
_NBSP_CHARS = "\u00a0\u202f"


def _language_rule_files(codes: list[str]) -> dict[str, list[dict]]:
    import json
    out = {}
    for c in codes:
        f = LANG_DIR / f"{c}.json"
        if f.is_file():
            out[c] = [r for r in json.loads(f.read_text(encoding="utf-8")).get("rules", []) if isinstance(r.get("check"), dict)]
    return out


def _masked(text: str, keep: list[tuple[int, int]] | None) -> str:
    """The text nodes of the book at their original offsets: tags, scripts, styles, svg, code and pre blocks, and (when `keep` is given)
    everything outside the kept ranges become spaces, so a match offset is an offset in the file and the line number is real."""
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))  # noqa: E731
    t = PROSE_DROP.sub(blank, text)
    t = re.sub(r"<!--.*?-->", blank, t, flags=re.S)
    t = re.sub(r"<[^>]*>", blank, t)
    if keep is not None:
        chars = list(re.sub(r"[^\n]", " ", t))
        src = list(t)
        for a, b in keep:
            chars[a:b] = src[a:b]
        t = "".join(chars)
    return t


def _lang_ranges(text: str, code: str) -> list[tuple[int, int]]:
    out = []
    for t in htmlscan.tags(text):
        if t.closing or t.void or t.name in ("html", "body", "head") or t.attrs.get("lang", "").lower().split("-")[0] != code:
            continue
        out.append((t.start, htmlscan.element_end(text, t)))
    return out


def _language_rules(text: str, view: dict) -> list[dict]:
    """The `check` of each rule in scripts/data/languages/<code>.json, run on the book text written in that language (a warning with line and
    offset, never a failure: typography is advice). One content language: the whole book text. Several: the elements marked lang=<code>."""
    langs = view.get("content_languages") or []
    out = []
    for code, rules in _language_rule_files(langs).items():
        keep = None if len(langs) == 1 else _lang_ranges(text, code)
        if keep is not None and not keep:
            continue
        body = _masked(text, keep)
        for r in rules:
            c = r["check"]
            if c.get("kind") == "single-letter-nbsp":
                words = "".join(re.escape(w) for w in c["words"])
                pat = re.compile(rf"(?<![\w\u2019'-])([{words}{words.upper()}])[ \t]+(?=[^\W_])")
                what = "a one-letter word is followed by an ordinary space (use a no-break space)"
            elif c.get("kind") == "low-opening-quote":
                pat = re.compile("[" + "".join(re.escape(x) for x in c["flag"]) + "]")
                what = "a quotation mark that is not the language's own (open low, close high)"
            else:
                continue
            hits = []
            for m in pat.finditer(body):
                line = body.count("\n", 0, m.start()) + 1
                hits.append(f"line {line}, offset {m.start()}: {what}: \"{' '.join(_ctx(body, m, 24).split())}\"")
            out.append(row(f"lang:{code}:{r['id']}", "warn" if hits else "pass", r["text"],
                           "; ".join(hits[:4]) + (f"; {len(hits) - 4} more" if len(hits) > 4 else "") if hits else "no instance found"))
    return out


def _shape(frag: str) -> tuple:
    return tuple(t.name for t in htmlscan.tags(frag) if not t.closing and t.name in SHAPE_TAGS)


def _parity_rules(text: str, view: dict) -> list[dict]:
    langs = view["content_languages"]
    blocks: dict[str, dict[str, list]] = {}
    for t in htmlscan.tags(text):
        if t.closing or "data-key" not in t.attrs:
            continue
        lang = t.attrs.get("lang", "")
        end = htmlscan.element_end(text, t)
        blocks.setdefault(t.attrs["data-key"], {}).setdefault(lang, []).append(_shape(text[t.start:end]))
    probs = []
    if len(langs) > 1 and not blocks:
        probs.append(f"content_languages is {','.join(langs)} but the book has no per-language blocks (elements with lang= and data-key=)")
    for key, by in sorted(blocks.items()):
        extra = sorted(set(by) - set(langs))
        miss = sorted(set(langs) - set(by))
        if extra:
            probs.append(f"{key}: text in {','.join(extra)}, which is not in content_languages ({','.join(langs)})")
        if len(langs) > 1 and miss:
            probs.append(f"{key}: no {','.join(miss)} version")
        shapes = {lg: by[lg][0] for lg in by if lg in langs}
        if len({s for s in shapes.values()}) > 1:
            ref_lang = next(iter(shapes))
            for lg, s in shapes.items():
                if s != shapes[ref_lang]:
                    i = next((i for i, (x, y) in enumerate(zip(s, shapes[ref_lang])) if x != y), min(len(s), len(shapes[ref_lang])))
                    probs.append(f"{key}: {lg} and {ref_lang} differ in structure at block {i + 1} ({len(s)} vs {len(shapes[ref_lang])} blocks)")
                    break
    n = len(blocks)
    detail = "; ".join(probs[:5]) if probs else (f"{n} keyed block(s) in {','.join(langs)}" if n else f"one content language ({langs[0]})")
    return [row("lang:parity", "fail" if probs else "pass", f"every block exists in each content language ({','.join(langs)}) with the same structure", detail)]


def _self_rules(text: str, cfg: dict, doc: dict) -> list[dict]:
    out = []
    ds = book_css_decls(text)
    allowed = bookdata.motion_durations_ms(doc)
    bad = []
    for where, p, v in ds:
        if p in ("transition", "transition-duration", "transition-delay", "animation", "animation-duration", "animation-delay"):
            for m in re.finditer(r"(?<![\w.-])(\d*\.?\d+)(ms|s)\b", v):
                ms = float(m.group(1)) * (1000 if m.group(2) == "s" else 1)
                if ms != 0 and not any(abs(ms - a) < 0.5 for a in allowed):
                    bad.append(f"{p}: {m.group(0)} in {where[:40]} is not a duration token ({', '.join(f'{a:g}ms' for a in allowed) or 'the tokens define none'})")
    out.append(row("self:durations", "fail" if bad else "pass", "every CSS duration and delay is one of the motion tokens (or 0)",
                   "; ".join(bad[:4]) if bad else f"{sum(1 for _, p, _ in ds if 'transition' in p or 'animation' in p)} motion declaration(s)"))
    meta = re.search(r"<meta\b[^>]*name=[\"']bc-min-label[\"'][^>]*content=[\"'](\d+(?:\.\d+)?)[\"']", text, re.I)
    stated = float(meta.group(1)) if meta else None
    floor = float(cfg["min_label_px"])
    probs = []
    if stated is not None and stated != floor:
        probs.append(f"the book states a {stated:g} px minimum label size but book/book.json says {floor:g}")
    mn = stated if stated is not None else floor
    sizes = []
    for where, p, v in ds:
        if p in ("font-size", "font"):
            px, why = font_px(v, p)
            if why:
                probs.append(f"{where[:40]}: {why}")
            elif px is not None:
                sizes.append(px)
                if px < mn:
                    probs.append(f"{where[:40]}: {p} {v} is {px:g} px, under the book's minimum label size of {mn:g} px")
    out.append(row("self:font-size", "fail" if probs else "pass", f"no text under the book's minimum label size ({mn:g} px)",
                   "; ".join(probs[:4]) if probs else f"smallest declared size {min(sizes):g} px" if sizes else "no font sizes declared"))
    tok = bookdata.token_hexes(doc)
    cprobs = []
    n = 0
    for where, p, v in ds:
        if p.startswith("--") or "color" in p or p in ("background", "border", "outline", "fill", "stroke", "box-shadow", "text-shadow") \
                or p.startswith(("border", "outline", "background")):
            cols, badc = colours_in(v)
            n += len(cols)
            for c in cols:
                if c not in tok:
                    cprobs.append(f"{c} in {where[:40]} ({p}) is not a token")
            for b in badc:
                cprobs.append(f"{b} in {where[:40]} ({p}) is not a token colour")
    for t in htmlscan.tags(text):
        if t.closing:
            continue
        for k in ("fill", "stroke", "stop-color", "flood-color", "color"):
            v = t.attrs.get(k)
            if v and t.name not in ("img",):
                cols, badc = colours_in(v)
                n += len(cols)
                cprobs += [f"{c} in <{t.name} {k}> is not a token" for c in cols if c not in tok]
                cprobs += [f"{b} in <{t.name} {k}> is not a token colour" for b in badc]
    out.append(row("self:colours", "fail" if cprobs else "pass", "every colour the book uses is one of the brand's tokens",
                   "; ".join(sorted(set(cprobs))[:4]) if cprobs else f"{n} colour value(s), all tokens"))
    return out


# ---------------------------------------------------------------- reports

def lint_inputs(project: Path, book: Path) -> list[Path]:
    """Every file a lint run read: the book, tokens, manifest, facts, config, the FORBIDDEN sources and the mark artwork."""
    out = [book]
    for rel in ("assets/tokens/tokens.json", "FACTS.md", "book/book.json", "brief/BRIEF.md", "research/cliches.md"):
        if (project / rel).is_file():
            out.append(project / rel)
    out += bookdata.logo_files(project)
    return out


def write_report(project: Path, book: Path, results: list[dict], **extra) -> "Report":
    """A book-lint Report for `results` (not yet finished; the caller prints and exits with report.finish())."""
    from _common import Report
    rep = Report("book-lint", project, lint_inputs(project, book))
    for r in results:
        extra_r = {k: v for k, v in r.items() if k not in ("id", "status", "label")}
        rep.add(r["id"], r["status"], r["label"], **extra_r)
    rep.extra.update(extra)
    rep.extra["manifest_view_sha"] = bookdata.manifest_view_sha(project)
    return rep
