"""The brand book lint: every rule, as a function of the book text and the project's data. Standard library only.

Used by book_lint.py (the gate), book.py (a book that does not lint is not written), book_pdf.py and check. Each rule is one
result row {id, status, label, detail}; status is pass, fail, warn, info or skipped. See scripts/CONTRACT.md, "Brand book".
"""
from __future__ import annotations

import base64
import fnmatch
import hashlib
import html as _html
import re
import struct
import urllib.parse
from pathlib import Path
from typing import NamedTuple

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

def _at_statement(css: str, i: int) -> int:
    """The index just after the ';' that ends the statement at-rule (@layer a,b; @import url(x); @charset "utf-8";) starting at css[i], or -1 when a block opens first."""
    quote, depth = "", 0
    for k in range(i, len(css)):
        ch = css[k]
        if quote:
            quote = "" if ch == quote and css[k - 1] != "\\" else quote
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        elif not depth and ch == "{":
            return -1
        elif not depth and ch == ";":
            return k + 1
    return -1


def _flat_declarations(body: str) -> str:
    """The declarations of a style rule that holds nested rules, its own and those inside the nested blocks, as one body (what comes before a nested block's `{` after the
    last `;` is its selector, and is dropped)."""
    out, i = [], 0
    while True:
        j = body.find("{", i)
        if j < 0:
            return "".join(out) + body[i:]
        depth, k = 1, j + 1
        while k < len(body) and depth:
            depth += (body[k] == "{") - (body[k] == "}")
            k += 1
        before = body[i:j]
        out.append(before[:before.rfind(";") + 1] + _flat_declarations(body[j + 1:k - 1]) + ";")
        i = k


def css_rules(css: str, ctx: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], str, str, bool]]:
    """Every block with no block inside it as (the at-rules around it, its prelude, its body, whether it holds nested rules): the @media and @keyframes that css_blocks loses.
    A statement at-rule (@layer a,b; @import url(x); @charset "utf-8";) ends at its ';' and comes out as (the at-rules around it, the statement with its ';', "", False), so that
    the rule after it is read. A style rule that holds nested rules (CSS nesting) is one block whose body is every declaration inside it, its own and the nested ones, with True."""
    out, i = [], 0
    while i < len(css):
        k = i
        while k < len(css) and css[k].isspace():
            k += 1
        end = _at_statement(css, k) if css.startswith("@", k) else -1
        if end > 0:
            out.append((ctx, css[k:end].strip(), "", False))
            i = end
            continue
        j = css.find("{", i)
        if j < 0:
            break
        depth, k = 1, j + 1
        while k < len(css) and depth:
            depth += (css[k] == "{") - (css[k] == "}")
            k += 1
        body, head = css[j + 1:k - 1], css[i:j].strip()
        if "{" not in body:
            out.append((ctx, head, body, False))
        elif head.startswith("@"):
            out += css_rules(body, ctx + (head,))
        else:
            out.append((ctx, head, _flat_declarations(body), True))
        i = k
    return out


def css_blocks(css: str) -> list[tuple[str, str]]:
    return [(head, body) for _ctx, head, body, _nested in css_rules(css)]


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
        res += _motion_rules(project, text, view)
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
    own = _demo_allowance(text)
    bad = []
    for where, p, v in ds:
        if p in ("transition", "transition-duration", "transition-delay", "animation", "animation-duration", "animation-delay"):
            for m in re.finditer(r"(?<![\w.-])(\d*\.?\d+)(ms|s)\b", v):
                ms = float(m.group(1)) * (1000 if m.group(2) == "s" else 1)
                if ms != 0 and not any(abs(ms - a) < 0.5 for a in allowed + own(where)):
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


# ---------------------------------------------------------------- the motion rows: the book's CSS with its @media context, a small selector matcher, the cascade

class _Rule(NamedTuple):
    media: tuple[str, ...]                                   # the at-rules around the rule (@media ...)
    sels: list[tuple[str, tuple[int, int, int], list | None]]   # each selector of its list: (text, specificity, compounds; None when the lint cannot read it)
    decls: list[tuple[str, str, bool, int]]                  # (property, value, !important, place in the source)
    nested: bool = False                                     # the rule holds nested rules: its decls are every declaration inside it, and the cascade does not apply it


class _El:
    """An element of the book as the motion rows need it: its tag, attributes, parent, element children and the offsets of its start tag and end."""
    __slots__ = ("tag", "attrs", "parent", "kids", "start", "end")

    def __init__(self, tag: str, attrs: dict, parent: "_El | None", start: int):
        self.tag, self.attrs, self.parent, self.kids, self.start, self.end = tag, attrs, parent, [], start, start


_TIME = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(ms|s)", re.I)
_ANIM_WORDS = {"none", "infinite", "normal", "reverse", "alternate", "alternate-reverse", "forwards", "backwards", "both", "running", "paused", "ease", "ease-in",
               "ease-out", "ease-in-out", "linear", "step-start", "step-end", "initial", "inherit", "unset", "revert"}
_TIMING_WORDS = {"linear", "ease", "ease-in", "ease-out", "ease-in-out", "step-start", "step-end"}
_REDUCE = re.compile(r"^(?:(?:only )?(?:screen|all) and )?\(prefers-reduced-motion:reduce\)$")


def _layers(value: str) -> list[list[str]]:
    """A comma list of space separated words; a function such as steps(2, end) is one word."""
    return [re.findall(r"[^\s(]+(?:\([^)]*\))?", layer) for layer in re.split(r",(?![^()]*\))", value) if layer.strip()]


def _ms(word: str) -> float | None:
    m = _TIME.fullmatch(word.strip())
    return None if not m else float(word.strip()[:-len(m.group(1))]) * (1000 if m.group(1).lower() == "s" else 1)


def _animation(value: str) -> tuple[list[str], float | None, bool, str, str]:
    """(the animation name of each layer of an `animation` value, the duration of its first layer in ms, whether a layer repeats forever, and of the first layer its
    iteration count and its timing function, as a shorthand that leaves them out sets them: 1 and ease); no name is `none`."""
    names, dur, forever, count, timing = [], None, False, "1", "ease"
    for i, words in enumerate(_layers(value)):
        names.append(next((w for w in words if not _TIME.fullmatch(w) and w.lower() not in _ANIM_WORDS and not re.fullmatch(r"[\d.]+", w)
                           and not w.lower().startswith(("steps(", "cubic-bezier(", "linear("))), "none"))
        if i == 0:
            dur = next((_ms(w) for w in words if _TIME.fullmatch(w)), None)
            count = next((w for w in words if re.fullmatch(r"\d*\.?\d+", w)), "1")   # the one bare number of the shorthand
            timing = next((w for w in words if w.lower() in _TIMING_WORDS or w.lower().startswith(("steps(", "cubic-bezier(", "linear("))), "ease")
        forever = forever or "infinite" in (w.lower() for w in words)
    return names, dur, forever, count, timing


def _animation_more(value: str) -> tuple[str, str, str, float]:
    """Of the first layer of an `animation` value: its direction, play state and fill mode (as a shorthand that leaves them out sets them: normal, running and none) and
    its delay in ms (the second time of the layer, else 0)."""
    words = (_layers(value) or [[]])[0]
    low = [w.lower() for w in words]
    pick = lambda options, default: next((w for w in low if w in options), default)   # noqa: E731
    times = [_ms(w) for w in words if _TIME.fullmatch(w)]
    return (pick(("normal", "reverse", "alternate", "alternate-reverse"), "normal"), pick(("running", "paused"), "running"), pick(("forwards", "backwards", "both"), "none"),
            times[1] if len(times) > 1 else 0.0)


def _longhands(prop: str, value: str) -> list[tuple[str, str]]:
    """The longhands the motion rows read from an `animation` or `transition` shorthand (the declaration itself is kept as well)."""
    if prop == "animation":
        names, dur, forever, count, timing = _animation(value)
        direction, play, fill, delay = _animation_more(value)
        return [("animation-name", ", ".join(names)), ("animation-duration", f"{bookdata.num_text(dur or 0)}ms"),
                ("animation-iteration-count", "infinite" if forever else count), ("animation-timing-function", timing),
                ("animation-direction", direction), ("animation-play-state", play), ("animation-fill-mode", fill), ("animation-delay", f"{bookdata.num_text(delay)}ms")]
    if prop == "transition":
        layers = _layers(value)
        return [("transition-duration", ", ".join(f"{bookdata.num_text(next((_ms(w) for w in words if _TIME.fullmatch(w)), 0.0) or 0.0)}ms" for words in layers)),
                ("transition-property", "none" if all(words[:1] == ["none"] for words in layers) else "all")]
    return []


def _declared(body: str) -> list[tuple[str, str, bool]]:
    """The declarations of a block or of a style attribute as (property, value, !important); each `animation` or `transition` is followed by the longhands the rows read."""
    out = []
    for prop, val in decls(body):
        imp = bool(re.search(r"!\s*important\s*$", val, re.I))
        val = re.sub(r"\s*!\s*important\s*$", "", val, flags=re.I)
        out += [(p2, v2, imp) for p2, v2 in [(prop, val)] + _longhands(prop, val)]
    return out


_TOKEN = re.compile(r"""(?P<ws>\s+)|(?P<comb>[>+~])|(?P<type>\*|[A-Za-z][\w-]*)|\#(?P<id>[\w-]+)|\.(?P<cls>[\w-]+)
    |\[\s*(?P<attr>[\w-]+)\s*(?:(?P<op>[~|^$*]?=)\s*(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>[^\]\s]+))\s*)?\]
    |::(?P<pe>[\w-]+)(?:\([^)]*\))?|:(?P<pc>[\w-]+)(?:\((?P<parg>[^)]*)\))?""", re.X)


def parse_selector(sel: str) -> list[tuple[str, dict]] | None:
    """A complex selector as [(the combinator before the compound, the compound)]; the compound is {type, ids, classes, attrs, pseudos, elements}. The lint reads
    type, #id, .class, [attr] forms, pseudo-classes and elements and the four combinators; anything else makes it None (the rule is not read)."""
    parts, comp, comb, pos, sel = [], None, " ", 0, sel.strip()
    while pos < len(sel):
        m = _TOKEN.match(sel, pos)
        if not m:
            return None
        pos = m.end()
        if m.group("ws") is not None or m.group("comb"):
            if comp is not None:
                parts.append((comb, comp))
                comp, comb = None, " "
            if m.group("comb"):
                comb = m.group("comb")
            continue
        if comp is None:
            comp = {"type": None, "ids": [], "classes": [], "attrs": [], "pseudos": [], "elements": []}
        if m.group("type"):
            comp["type"] = m.group("type").lower()
        elif m.group("id"):
            comp["ids"].append(m.group("id"))
        elif m.group("cls"):
            comp["classes"].append(m.group("cls"))
        elif m.group("attr"):
            val = next((g for g in (m.group("dq"), m.group("sq"), m.group("bare")) if g is not None), None)
            comp["attrs"].append((m.group("attr").lower(), m.group("op"), val))
        elif m.group("pe"):
            comp["elements"].append(m.group("pe"))
        else:
            comp["pseudos"].append(m.group("pc").lower())
    if comp is None:
        return None
    parts.append((comb, comp))
    return parts


def _specificity(parts: list[tuple[str, dict]]) -> tuple[int, int, int]:
    a = sum(len(c["ids"]) for _, c in parts)
    b = sum(len(c["classes"]) + len(c["attrs"]) + len(c["pseudos"]) for _, c in parts)
    c = sum((c["type"] not in (None, "*")) + len(c["elements"]) for _, c in parts)
    return a, b, c


def _compound_matches(el: _El, comp: dict, checked: frozenset, loose: bool = False) -> bool:
    if comp["elements"] or comp["type"] not in (None, "*", el.tag):
        return False
    classes = el.attrs.get("class", "").split()
    if any(i != el.attrs.get("id") for i in comp["ids"]) or any(c not in classes for c in comp["classes"]):
        return False
    for name, op, val in comp["attrs"]:
        v = el.attrs.get(name)
        if v is None or (op == "=" and v != val) or (op == "~=" and val not in v.split()) or (op == "|=" and v != val and not v.startswith(val + "-")) \
                or (op == "^=" and not (val and v.startswith(val))) or (op == "$=" and not (val and v.endswith(val))) or (op == "*=" and not (val and val in v)):
            return False
    # :checked is the state the row asks about; any other pseudo-class (:hover, :focus-visible, :not() ...) is a state the page is not in, or a condition the lint does
    # not evaluate: it matches nothing, and a rule that sets what a motion row reads is named in that row (`loose` takes them as true, to tell whether it could reach)
    if loose:
        return all(ps != "checked" or el.tag == "input" for ps in comp["pseudos"])
    return all(ps == "checked" and el.tag == "input" and el.attrs.get("id") in checked for ps in comp["pseudos"])


def _matches(el: _El, parts: list[tuple[str, dict]], i: int, checked: frozenset, loose: bool = False) -> bool:
    comb, comp = parts[i]
    if not _compound_matches(el, comp, checked, loose):
        return False
    if i == 0:
        return True
    par = el.parent
    if comb in (" ", ">"):
        while par is not None and par.tag != "#root":
            if _matches(par, parts, i - 1, checked, loose):
                return True
            if comb == ">":
                return False
            par = par.parent
        return False
    sibs = par.kids[:par.kids.index(el)] if par is not None else []
    return bool(sibs) and (_matches(sibs[-1], parts, i - 1, checked, loose) if comb == "+" else any(_matches(x, parts, i - 1, checked, loose) for x in sibs))


def _split_list(sel: str) -> list[str]:
    return [x.strip() for x in re.split(r",(?![^()\[\]]*[)\]])", sel) if x.strip()]


def _norm_sel(sel: str) -> str:
    return re.sub(r"\s*([>+~,])\s*", r"\1", re.sub(r"\s+", " ", sel.strip()))


def _media_query(at_rule: str) -> str:
    return re.sub(r"\s*:\s*", ":", re.sub(r"\s+", " ", at_rule[6:].strip().lower()))


def _media_holds(media: tuple[str, ...], mode: str) -> bool:
    """Whether the rule applies when the page is shown on a screen (mode "screen"), with reduced motion asked for ("reduce") or printed ("print"). A condition
    the lint does not read is taken to hold: a rule under it may apply."""
    def term(t: str) -> bool:
        t = re.sub(r"^only ", "", t.strip())
        return {"print": mode == "print", "screen": mode != "print", "(prefers-reduced-motion:reduce)": mode == "reduce",
                "(prefers-reduced-motion:no-preference)": mode != "reduce"}.get(t, True)
    return all(any(all(term(t) for t in alt.split(" and ")) for alt in _media_query(m).split(",")) for m in media if m.lower().startswith("@media"))


_UNREAD_AT = ("@layer", "@scope", "@container", "@supports")


def _unevaluated(media: tuple[str, ...]) -> tuple[str, ...]:
    """The at-rules around a rule that the cascade does not evaluate: a layer changes who wins, @scope which elements a rule reaches, @container and @supports whether it applies."""
    return tuple(m for m in media if m.lower().startswith(_UNREAD_AT))


def _in_reduce_block(media: tuple[str, ...]) -> bool:
    return any(_REDUCE.match(_media_query(m)) for m in media if m.lower().startswith("@media"))


def _only_without_reduce(media: tuple[str, ...]) -> bool:
    return any("(prefers-reduced-motion:no-preference)" in _media_query(m).split(" and ") for m in media if m.lower().startswith("@media"))


def style_rules(text: str) -> tuple[list[_Rule], dict[str, list[tuple[str, str]]], list[str]]:
    """The style rules of the book's <style> elements in source order, its @keyframes (name -> the frames as (selector without spaces, declarations as `p:v;p:v`); a
    @keyframes with no name is kept under ""), and the data: URIs of its url()s: a picture is a megabyte of base64 that the rules are not read through, so each stands
    in the rules as `data:@N` for the N-th of the list. A layer statement (`@layer a, b;`) is a rule with no declarations whose one selector is the statement, and a rule that
    holds nested rules has `nested` set: neither is applied by the cascade, and _unread names them."""
    rules, frames, uris, seq = [], {}, [], 0

    def stand_in(m: re.Match) -> str:
        uris.append(m.group(2))
        return f"url(data:@{len(uris) - 1})"
    for m in re.finditer(r"<style\b[^>]*>(.*?)</style\s*>", text, re.I | re.S):
        css = re.sub(r"url\(\s*(['\"]?)(data:[^)'\"]*)\1\s*\)", stand_in, m.group(1), flags=re.I)
        for ctx, head, body, nested in css_rules(re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
            kf = next((c for c in ctx if c.lower().startswith("@keyframes")), None)
            if kf:
                frames.setdefault(kf[len("@keyframes"):].strip(), []).append((re.sub(r"\s+", "", head), ";".join(f"{p}:{' '.join(v.split())}" for p, v in decls(body))))
                continue
            if head.startswith("@"):
                if head.lower().startswith("@layer") and head.endswith(";"):   # a layer statement orders layers, which the cascade does not evaluate: _unread names it
                    rules.append(_Rule(ctx, [(_norm_sel(head[:-1]), (0, 0, 0), None)], []))
                continue
            ds = []
            for p2, v2, imp in _declared(body):
                seq += 1
                ds.append((p2, v2, imp, seq))
            sels = []
            for sel in _split_list(head):
                parts = parse_selector(sel)
                sels.append((sel, _specificity(parts) if parts else (0, 0, 0), parts))
            rules.append(_Rule(ctx, sels, ds, nested))
    return rules, frames, uris


def _winner(rules: list[_Rule], el: _El, prop: str, *, checked: frozenset = frozenset(), mode: str = "screen") -> tuple[str | None, bool, bool]:
    """(the value of `prop` on `el`, whether it is its style attribute's, whether it is !important) once the rules that apply and the style attribute have been weighed:
    importance first, then the style attribute over any rule, then specificity, then the later declaration (so an inline declaration beats a rule of the same importance and
    an !important rule beats an inline one that is not); (None, False, False) when nothing sets it. A rule inside @layer, @scope, @container or @supports, and a rule that holds
    nested rules, is not applied: the cascade does not evaluate them (_unread names those that set what a row reads)."""
    best, key = None, None
    for r in rules:
        if not _media_holds(r.media, mode) or _unevaluated(r.media) or r.nested:
            continue
        spec = max((sp for _t, sp, parts in r.sels if parts and _matches(el, parts, len(parts) - 1, checked)), default=None)
        if spec is None:
            continue
        for p, v, imp, seq in r.decls:
            if p == prop and (key is None or (imp, 0, spec, seq) > key):
                best, key = v, (imp, 0, spec, seq)
    for n, (p, v, imp) in enumerate(_declared(_strip_data(el.attrs.get("style", ""))), 1):
        if p == prop and (key is None or (imp, 1, (0, 0, 0), n) > key):
            best, key = v, (imp, 1, (0, 0, 0), n)
    return best, key is not None and key[1] == 1, key is not None and bool(key[0])


def _cascade(rules: list[_Rule], el: _El, prop: str, *, checked: frozenset = frozenset(), mode: str = "screen") -> str | None:
    """The value of `prop` on `el` (see _winner); None when nothing sets it."""
    return _winner(rules, el, prop, checked=checked, mode=mode)[0]


def _dom(text: str) -> _El:
    """The elements of the book as a tree (the root is "#root"); an end tag closes the nearest open element of its name."""
    root = _El("#root", {}, None, 0)
    stack = [root]
    for t in htmlscan.tags(text):
        if t.closing:
            for k in range(len(stack) - 1, 0, -1):
                if stack[k].tag == t.name:
                    for e in stack[k:]:
                        e.end = t.end
                    del stack[k:]
                    break
            continue
        e = _El(t.name, t.attrs, stack[-1], t.start)
        stack[-1].kids.append(e)
        if t.void:
            e.end = t.end
        else:
            stack.append(e)
    for e in stack[1:]:
        e.end = len(text)
    return root


def _walk(el: _El):
    todo = [el]
    while todo:
        e = todo.pop()
        yield e
        todo.extend(reversed(e.kids))


def _motion_demos(root: _El) -> list[dict]:
    """Every <figure data-motion-demo> of the book with its parts: the two checkboxes (by the start of their ids), their labels, the flipbook (the strip <img>), the
    reduced still, and the four states of the checkboxes as the sets of ids that are checked."""
    out = []
    for fig in (e for e in _walk(root) if e.tag == "figure" and "data-motion-demo" in e.attrs):
        els = list(_walk(fig))

        def one(tag: str, cls: str) -> "_El | None":
            return next((e for e in els if e.tag == tag and cls in e.attrs.get("class", "").split()), None)
        boxes = [e for e in els if e.tag == "input" and e.attrs.get("type", "").lower() == "checkbox"]
        d = {"case": fig.attrs["data-motion-demo"], "fig": fig, "els": els, "labels": [e for e in els if e.tag == "label"],
             "flip": next((e for e in els if "motion-flip" in e.attrs.get("class", "").split()), None), "reduced": one("img", "motion-reduced"),
             "replay": next((e for e in boxes if e.attrs.get("id", "").startswith("bc-replay-")), None),
             "slow": next((e for e in boxes if e.attrs.get("id", "").startswith("bc-slow-")), None)}
        ids = [(d[k].attrs["id"] if d[k] else None) for k in ("replay", "slow")]
        d["states"] = {(r, s): frozenset(i for i, on in zip(ids, (r, s)) if on and i) for r in (0, 1) for s in (0, 1)}
        out.append(d)
    return out


_STOPPING = {"animation-name": lambda v: all(n.strip().lower() == "none" for n in v.split(",")),
          "transition-property": lambda v: all(n.strip().lower() == "none" for n in v.split(",")),
          "transition-duration": lambda v: not any(_ms(w) for w in v.split(","))}   # the longhands that switch a motion off, and the values that do it
_STOP_LONGHANDS = {"animation": ("animation-name",), "transition": ("transition-property", "transition-duration")}


def _best(r: _Rule, prop: str) -> tuple[str, str, bool, int] | None:
    """The declaration of `prop` that wins inside the rule: an !important one before any other, and the later of two of the same importance."""
    return max((d for d in r.decls if d[0] == prop), key=lambda d: (d[2], d[3]), default=None)


def _stops(r: _Rule, kind: str) -> dict[str, tuple[bool, int]]:
    """The longhands the rule switches animations (kind "animation": animation-name none) or transitions off with (transition-property none, a transition-duration of 0), each with
    the importance and the place of the declaration that wins in the rule; empty when the rule switches nothing off."""
    wins = {lh: _best(r, lh) for lh in _STOP_LONGHANDS[kind]}
    return {lh: (d[2], d[3]) for lh, d in wins.items() if d and _STOPPING[lh](d[1])}


def _starts(r: _Rule) -> list[tuple[str, str, dict[str, bool]]]:
    """What the rule starts, as (kind, words, {longhand: !important}): ("animation", "the animation <names>", animation-name) and ("transition", "a transition" with a duration
    above 0, transition-duration and, when the rule sets one, transition-property): the longhands a stop has to win on, each as the declaration that wins in the rule has it."""
    out = []
    name = _best(r, "animation-name")
    live = [n.strip() for n in name[1].split(",") if n.strip().lower() not in ("", "none")] if name else []
    if live:
        out.append(("animation", "the animation " + ", ".join(live), {"animation-name": name[2]}))
    dur, prop = _best(r, "transition-duration"), _best(r, "transition-property")
    if dur and any(_ms(w) for w in dur[1].split(",")):
        out.append(("transition", "a transition", {"transition-duration": dur[2], **({"transition-property": prop[2]} if prop else {})}))
    return out


def _meet(a: tuple, b: tuple) -> bool:
    """Whether one element can be selected by both selectors (each as _Rule.sels holds it): the same text, or last compounds that agree on the tag, the id and the pseudo-element.
    A selector the lint cannot read meets only its own text."""
    if _norm_sel(a[0]) == _norm_sel(b[0]):
        return True
    if a[2] is None or b[2] is None:
        return False
    ca, cb = a[2][-1][1], b[2][-1][1]
    return len({c["type"] for c in (ca, cb)} - {None, "*"}) < 2 and len(set(ca["ids"]) | set(cb["ids"])) < 2 and ca["elements"] == cb["elements"]


def _gaps_under_reduced_motion(rules: list[_Rule], text: str) -> tuple[list[str], int, list[str]]:
    """-> (the rules that start an animation or a transition and are not switched off under prefers-reduced-motion: reduce, how many such rules the book has, the stops the
    cascade does not look at). A rule is switched off by a rule inside @media (prefers-reduced-motion: reduce) for the same selector (or for *) that sets animation: none
    (animation-name: none), or transition: none (a transition-property of none or a transition-duration of 0) and that wins on that longhand against every rule that can select the
    same element and sets it to a value that does not stop the motion: importance first, then specificity, then the later declaration (the start's own declarations too, so a start
    marked !important is switched off only by an !important stop, and a * only with !important, which an !important rule for a class outweighs). A stop that wins on another
    longhand counts (`transition-property: none` against an important duration). A rule that starts the same kind of motion under another selector is checked for itself; one
    that only sets a longhand (`main .y { transition-property: color }`) has to be switched off under its own selector too. A stop inside @layer, @scope, @container or
    @supports, or in a rule that holds nested rules, is not counted, and is named: the cascade does not evaluate them."""
    gaps, n, unread = [], 0, []
    live = [q for q in rules if _media_holds(q.media, "reduce") and not _unevaluated(q.media) and not q.nested]   # what applies when the preference is on, as the cascade reads it
    alone = {id(q): {k for k, *_ in _starts(q)} if not (_in_reduce_block(q.media) or _only_without_reduce(q.media)) else set() for q in live}   # the kinds a rule is checked for itself

    def outweighing(sel, lh, weight, kind, q, start=None):
        """The selectors of the rules other than the stop q that can select what `sel` selects, set `lh` to a value that does not stop the motion and outweigh `weight`; the
        start rule's own declarations are weighed too when it sits where the cascade does not look (an !important start in @supports needs an !important stop all the same)."""
        pool = live if start is None or any(p is start for p in live) else live + [start]
        for p in pool:
            d = _best(p, lh)
            if p is q or d is None or _STOPPING[lh](d[1]):
                continue
            kinds = alone[id(p)] if id(p) in alone else {k for k, *_ in _starts(p)}
            for y in p.sels:
                if _meet(sel, y) and (d[2], y[1], d[3]) > weight and (kind not in kinds or _norm_sel(y[0]) == _norm_sel(sel[0])):
                    yield y

    def covered(sel, kind, seen, start=None):
        """-> (whether a rule in @media (prefers-reduced-motion: reduce) for `sel` or `*` wins on a longhand that stops `kind` against every rule that outweighs it, the first
        selector that outweighs a stop and is not `sel`'s own, else None)"""
        want, blame = _norm_sel(sel[0]), None
        for q in live:
            if not _in_reduce_block(q.media):
                continue
            for x_text, _sp, _parts in q.sels:
                x = _norm_sel(x_text)
                if x not in (want, "*"):
                    continue
                for lh, (imp, seq) in _stops(q, kind).items():
                    weight = (imp, sel[1] if x == want else (0, 0, 0), seq)
                    hit = next((y for y in outweighing(sel, lh, weight, kind, q, start) if _norm_sel(y[0]) in seen | {want} or not covered(y, kind, seen | {want})[0]), None)
                    if hit is None:
                        return True, None
                    blame = blame or (hit if _norm_sel(hit[0]) != want else None)
        return False, blame

    def not_looked_at(sel, kind):
        """The rules in @media (prefers-reduced-motion: reduce) for `sel` or `*` that would switch the motion off, from where the cascade does not look, as _unread words them."""
        want = _norm_sel(sel[0])
        return [f"{_norm_sel(x_text)} (sets {kind})" + (f" inside {' and '.join(_unevaluated(q.media))}" if _unevaluated(q.media) else "") + (" with nested rules" if q.nested else "")
                for q in rules if _in_reduce_block(q.media) and _media_holds(q.media, "reduce") and (_unevaluated(q.media) or q.nested) and _stops(q, kind)
                for x_text, _sp, _parts in q.sels if _norm_sel(x_text) in (want, "*")]

    for r in rules:
        if _in_reduce_block(r.media) or _only_without_reduce(r.media):
            continue
        for kind, what, against in _starts(r):
            n += 1
            imp = any(against.values())
            off = 'animation: none' if kind == 'animation' else 'transition: none'
            for sel in r.sels:
                if _unevaluated(r.media) or r.nested:   # a start where the cascade does not look: weighed as if it applies, and named
                    unread.append(f"{_norm_sel(sel[0])} (starts {kind})" + (f" inside {' and '.join(_unevaluated(r.media))}" if _unevaluated(r.media) else "")
                                  + (" with nested rules" if r.nested else ""))
                ok, blame = covered(sel, kind, frozenset(), r)
                if ok:
                    continue
                if blame:
                    gaps.append(f"{sel[0]!r} starts {what}{' with !important' if imp else ''} and the {off} for it in @media (prefers-reduced-motion: reduce) is outweighed by {blame[0]!r}")
                else:
                    gaps.append(f"{sel[0]!r} starts {what}{' with !important' if imp else ''} and no later rule in @media (prefers-reduced-motion: reduce) sets "
                                + (f"{off} !important for it" if imp else f"{off} for it (or for * with !important)"))
                unread += not_looked_at(sel, kind)
    for t in htmlscan.tags(text):   # an inline style cannot be switched off by a media query
        st = t.attrs.get("style") if not t.closing else None
        if st:
            pseudo = _Rule((), [], [(p2, v2, imp, 0) for p2, v2, imp in _declared(_strip_data(st))])
            for _kind, what, _against in _starts(pseudo):
                n += 1
                gaps.append(f"<{t.name} style> starts {what}; an inline style cannot be switched off under reduced motion: move it into a rule")
    return gaps, n, list(dict.fromkeys(unread))


def _zero(v: str) -> bool:
    try:
        return float(v[:-1] if v.endswith("%") else v) == 0
    except ValueError:
        return False


def _unseen(el: _El, rules: list[_Rule], st: frozenset, *, opacity: bool) -> str | None:
    """Why `el` is not shown on a screen when the checkboxes are in the state `st`, else None: it or an ancestor has the hidden or the inert attribute, is
    display: none, or is visibility: hidden (the innermost value that says visible or hidden counts, as visibility is inherited), and with `opacity` is at opacity 0
    (any ancestor at 0 makes the product 0). A style attribute weighs above the rules of its importance (_winner). Outside the reduced-motion and print media: the book as a screen shows it."""
    def value(n: _El, prop: str) -> tuple[str, str]:   # (the value, and who says it)
        v, own, _imp = _winner(rules, n, prop, checked=st)
        return (v or "").strip().lower(), "its style says" if own else "a rule says"
    seen = False   # an element between this one and the ancestor said visibility: visible, which an ancestor's hidden does not outweigh
    n = el
    while n is not None and n.tag != "#root":
        who = f"<{n.tag}{' ' + n.attrs['id'] if n.attrs.get('id') else ''}>"
        where = "" if n is el else f" (on its ancestor {who})"
        for attr in ("hidden", "inert"):
            if attr in n.attrs:
                return f"it has the {attr} attribute" if n is el else f"its ancestor {who} has the {attr} attribute"
        v, said = value(n, "display")
        if v == "none":
            return f"{said} display: none{where}"
        v, said = value(n, "visibility")
        if not seen:
            if v in ("hidden", "collapse"):
                return f"{said} visibility: {v}{where}"
            seen = v == "visible"
        if opacity:
            v, said = value(n, "opacity")
            if _zero(v):
                return f"{said} opacity: 0{where}"
        n = n.parent
    return None


def _hidden_from_keyboard(d: dict, which: str, rules: list[_Rule]) -> str | None:
    """Why the checkbox is out of the keyboard's reach (outside the reduced-motion and print media), else None: it is disabled or has a negative tabindex, or it or an
    ancestor is hidden, inert, display: none or visibility: hidden."""
    el = d[which]
    if "disabled" in el.attrs:
        return "it has the disabled attribute"
    if el.attrs.get("tabindex", "0").strip().startswith("-"):
        return "it has a negative tabindex"
    for st in d["states"].values():
        why = _unseen(el, rules, st, opacity=False)
        if why:
            return why
    return None


def _reduced_problems(d: dict, rules: list[_Rule]) -> list[str]:
    """What is wrong with one demo under reduced motion: the flipbook must be hidden and have no animation, the reduced still shown, the controls hidden."""
    out, case = [], d["case"]
    if d["flip"] is None:
        return [f"{case}: no flipbook (an element with the class motion-flip)"]
    for st in d["states"].values():
        shown = _cascade(rules, d["flip"], "display", checked=st, mode="reduce")
        anim = _cascade(rules, d["flip"], "animation-name", checked=st, mode="reduce")
        if (shown or "inline").strip().lower() != "none":
            out.append(f"{case}: the flipbook is shown under reduced motion (display: {shown or 'the default'})")
            break
        if anim and any(n.strip().lower() != "none" for n in anim.split(",")):
            out.append(f"{case}: the flipbook still has an animation under reduced motion ({anim}); it needs animation: none")
            break
    if d["reduced"] is None:
        out.append(f"{case}: no reduced still (an <img class=\"motion-reduced\">)")
    elif (_cascade(rules, d["reduced"], "display", mode="reduce") or "inline").strip().lower() == "none":
        out.append(f"{case}: the reduced still is not shown under reduced motion (display: none)")
    for e in [d["replay"], d["slow"], *d["labels"]]:
        if e is not None and (_cascade(rules, e, "display", mode="reduce") or "inline").strip().lower() != "none":
            out.append(f"{case}: <{e.tag}{' ' + e.attrs['id'] if 'id' in e.attrs else ''}> is shown under reduced motion, where the flipbook it controls is not")
            break
    return out


def _first_unseen(el: _El, rules: list[_Rule], d: dict, *, opacity: bool) -> str | None:
    """Why `el` is not shown on a screen in some state of the demo's two checkboxes (the first reason), else None."""
    return next(filter(None, (_unseen(el, rules, st, opacity=opacity) for st in d["states"].values())), None)


def _steps_differ(frames: list[tuple[str, str]], want: dict[float, str]) -> str | None:
    """How the keyframes of a flipbook (as style_rules reads them) differ from the steps frames.json gives ({percent: `object-position:<x> 0`}), else None."""
    got = {}
    for sel, body in frames:
        for part in sel.split(","):
            part = part.strip().lower()
            pct = 0.0 if part == "from" else 100.0 if part == "to" else float(part[:-1]) if re.fullmatch(r"\d*\.?\d+%", part) else None
            if pct is not None:
                got[pct] = body   # a later keyframe for the same percent wins
    for pct in sorted(set(got) | set(want)):
        at = bookdata.num_text(pct, 2)
        if pct not in got:
            return f"no keyframe at {at} %, where frames.json has a still"
        if pct not in want:
            return f"a keyframe at {at} % has no still in frames.json"
        if got[pct] != want[pct]:
            return f"at {at} % it has `{got[pct]}`, frames.json gives `{want[pct]}`"
    return None


def _replay_problems(d: dict, rules: list[_Rule], kfs: dict, text: str, doc: dict | None) -> list[str]:
    """What is wrong with one demo's controls and flipbook: both checkboxes with an id, a label with text, the keyboard's reach, the labels and the flipbook shown on a
    screen, and a new animation-name (so a new run) for every change of either box, 4 x data-length-ms for the slow one, played once with step-end, forwards (direction
    normal), running, held at both ends (fill mode both) and at once (delay 0), @keyframes that exist, are the same for the four names and step through the stills `doc`
    (frames.json) lists, each at its percent."""
    out, case, fig = [], d["case"], d["fig"]
    try:
        length = float(fig.attrs.get("data-length-ms", ""))
    except ValueError:
        length = 0.0
    if not length > 0:
        out.append(f"{case}: data-length-ms is not a number above 0")
    for which in ("replay", "slow"):
        el = d[which]
        if el is None:
            out.append(f"{case}: no checkbox whose id starts with bc-{which}-")
            continue
        id_ = el.attrs["id"]
        mine = [x for x in d["labels"] if x.attrs.get("for") == id_]
        if not mine:
            out.append(f"{case}: #{id_} has no <label for=\"{id_}\">")
        elif not any(htmlscan.visible_text(text[x.start:x.end], with_attributes=False).strip() for x in mine):
            out.append(f"{case}: the label of #{id_} has no visible text")
        for x in mine:
            why = _first_unseen(x, rules, d, opacity=True)
            if why:
                out.append(f"{case}: the label of #{id_} is not shown on a screen: {why}")
                break
        why = _hidden_from_keyboard(d, which, rules)
        if why:
            out.append(f"{case}: #{id_} is out of the keyboard's reach: {why}")
    if d["flip"] is None:
        return out + [f"{case}: no flipbook (an element with the class motion-flip)"]
    why = _first_unseen(d["flip"], rules, d, opacity=True)
    if why:
        out.append(f"{case}: the flipbook is not shown on a screen: {why}")
    odd = _picture(d["flip"])[2]
    if odd:
        out.append(_odd_source(case, odd))
    for st in d["states"].values():   # an animation is below an !important declaration in the cascade: the keyframes cannot move what one holds
        pos, _own, imp = _winner(rules, d["flip"], "object-position", checked=st)
        if imp:
            out.append(f"{case}: the flipbook has object-position: {pos} !important, which the keyframes cannot override, so the replay is frozen")
            break
    if d["replay"] is None or d["slow"] is None:
        return out
    got = {}
    for (r, s), st in d["states"].items():
        name = _cascade(rules, d["flip"], "animation-name", checked=st)
        dur = _cascade(rules, d["flip"], "animation-duration", checked=st)
        count = (_cascade(rules, d["flip"], "animation-iteration-count", checked=st) or "1").split(",")[0].strip().lower()
        timing = re.split(r",(?![^()]*\))", _cascade(rules, d["flip"], "animation-timing-function", checked=st) or "")[0].strip()   # the first of a list: steps(1, end) is one
        direction, play, fill = ((_cascade(rules, d["flip"], f"animation-{k}", checked=st) or default).split(",")[0].strip().lower()
                                 for k, default in (("direction", "normal"), ("play-state", "running"), ("fill-mode", "none")))
        delay = (_cascade(rules, d["flip"], "animation-delay", checked=st) or "0s").split(",")[0].strip()
        got[(r, s)] = (name or "none").strip()
        state = f"replay {'checked' if r else 'unchecked'}, slow {'checked' if s else 'unchecked'}"
        if got[(r, s)].lower() == "none":
            out.append(f"{case}: the flipbook has no animation ({state})")
            continue
        ms = _ms((dur or "").split(",")[0])
        want = 4 * length if s else length
        if ms is None or abs(ms - want) >= 0.5:
            out.append(f"{case}: the flipbook runs for {bookdata.num_text(ms) + ' ms' if ms is not None else 'no set time'} ({state}), not {bookdata.num_text(want)} ms "
                       f"({'4 x ' if s else ''}data-length-ms)")
        if count == "infinite":
            out.append(f"{case}: the flipbook repeats forever ({state}); it plays once")
        elif not _is_one(count):
            out.append(f"{case}: the flipbook plays {count} times ({state}); it plays once")
        if re.sub(r"\s+", "", (timing or "ease").lower()) not in ("step-end", "steps(1,end)", "steps(1,jump-end)", "steps(1)"):
            out.append(f"{case}: the flipbook's timing function is {timing or 'ease (the default)'} ({state}), not step-end: each still must hold until the next")
        if direction != "normal":
            out.append(f"{case}: the flipbook's direction is {direction} ({state}), not normal: the stills must play in order, once")
        if play != "running":
            out.append(f"{case}: the flipbook's play state is {play} ({state}), not running: it would not play")
        if fill != "both":
            out.append(f"{case}: the flipbook's fill mode is {fill} ({state}), not both: it must show the first still before it starts and stay on the last when it ends")
        if _ms(delay) != 0:   # a delay that cannot be read as a time is not 0 either
            out.append(f"{case}: the flipbook's delay is {delay} ({state}), not 0: it must start at once")
        if got[(r, s)] not in kfs:
            out.append(f"{case}: there is no @keyframes {got[(r, s)]} ({state})")
    for a, b, what in (((0, 0), (1, 0), "checking the replay box"), ((0, 0), (0, 1), "checking the slow box"),
                       ((1, 0), (1, 1), "checking the slow box with the replay box checked"), ((0, 1), (1, 1), "checking the replay box with the slow box checked")):
        if got[a] == got[b]:
            out.append(f"{case}: {what} does not change the flipbook's animation-name (still {got[a]}), so the replay would not start again")
    named = [n for n in dict.fromkeys(got.values()) if n in kfs]
    if len({repr(kfs[n]) for n in named}) > 1:
        out.append(f"{case}: the @keyframes of {', '.join(named)} are not the same")
    if doc is not None:
        want = {float(p): f"object-position:{x} 0" for p, x in bookdata.flipbook_steps(doc)}
        for n in named:
            why = _steps_differ(kfs[n], want)
            if why:
                out.append(f"{case}: the @keyframes {n} do not step through the stills of frames.json: {why}")
                break
    return out


def _is_one(count: str) -> bool:
    try:
        return float(count) == 1
    except ValueError:
        return False


def _png_dims(b: bytes) -> tuple[int, int] | None:
    return struct.unpack(">II", b[16:24]) if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24 else None


def _data_png(src: str) -> bytes | None:
    m = re.match(r"(?is)^\s*data:image/png;base64,(.*)$", src)
    try:
        return base64.b64decode(m.group(1), validate=True) if m else None
    except ValueError:
        return None


def _picture(el: "_El | None") -> tuple[str | None, float, str | None]:
    """(the picture an <img> shows, its density, the <source> that keeps the lint from knowing it): the first candidate (`data:... 2x` is 2) of the srcset of the first <source>
    before it in its <picture> (the strip is there; the img's own src is a 1 x 1 stand-in), else of its own srcset, else its src (1). That <source> is read only when it has no
    media attribute and its type is absent or image/png: a browser skips one with a media that does not match or a type it does not know, and then draws the stand-in, and the lint
    cannot tell: then there is no picture, and the third answer is that <source> written out (`<source type="image/x-nope">`)."""
    if el is None:
        return None, 1.0, None
    par = el.parent
    before = par.kids[:par.kids.index(el)] if par is not None and par.tag == "picture" else []
    source = next((k for k in before if k.tag == "source" and k.attrs.get("srcset", "").strip()), None)
    if source is not None and ("media" in source.attrs or "type" in source.attrs and source.attrs["type"].strip().lower() != "image/png"):
        return None, 1.0, "<source" + "".join(f' {a}="{source.attrs[a]}"' for a in ("media", "type") if a in source.attrs) + ">"
    ss = source.attrs["srcset"].strip() if source is not None else el.attrs.get("srcset", "").strip()
    if not ss:
        return el.attrs.get("src"), 1.0, None
    parts = ss.split(None, 1)   # a data: URI holds commas but no space: the first word is the URL, the rest its descriptor
    m = re.fullmatch(r"(\d*\.?\d+)x", parts[1].split(",")[0].strip()) if len(parts) > 1 else None
    return parts[0].rstrip(","), float(m.group(1)) if m else 1.0, None


def _odd_source(case: str, source: str) -> str:
    """The sentence motion:replay and motion:stills share for a <source> that _picture does not read."""
    return (f"{case}: the flipbook's {source} may not be the one a browser takes the strip from: it skips a <source> with a media attribute that does not match or a type that is not "
            "image/png, and then draws the 1 x 1 stand-in (the strip's <source> needs no media attribute and type=\"image/png\", or none)")


def _px(v: str | None) -> float | None:
    m = re.fullmatch(r"\s*(\d*\.?\d+)(?:px)?\s*", v or "")
    return float(m.group(1)) if m else None


def _stills_problems(project: Path, d: dict, rules: list[_Rule], doc: dict | None, bad: list[str]) -> tuple[list[str], list[str]]:
    """-> (what is wrong, what only deserves a warning) for one demo: its flipbook (the strip) and reduced still against the files frames.json lists, its
    data-length-ms and data-frames against frames.json, and the flipbook's size, density and fit. `doc` is frames.json (None, and `bad` says why, when it cannot be read)."""
    case, fig = d["case"], d["fig"]
    folder = bookdata.case_folder(case)
    if doc is None:
        return [f"{case}: {bad[0]}"], []
    out, warn = [], []
    if doc["case"] != case:
        return [f"{case}: {bookdata.FRAMES_DIR}/{folder}/frames.json is for the case {doc['case']!r}"], []
    older = "the book shows stills older than motion/frames: run brand-creator book"
    try:
        if abs(float(fig.attrs.get("data-length-ms", "")) - doc["length_ms"]) >= 0.0005:
            out.append(f"{case}: data-length-ms is {fig.attrs.get('data-length-ms')}, frames.json says {bookdata.num_text(doc['length_ms'])} ({older})")
    except ValueError:
        out.append(f"{case}: data-length-ms is not a number")
    if fig.attrs.get("data-frames") != str(len(doc["frames"])):
        out.append(f"{case}: data-frames is {fig.attrs.get('data-frames')}, frames.json lists {len(doc['frames'])} ({older})")
    flip = d["flip"]
    url, density, odd = _picture(flip)
    shown = {"reduced": d["reduced"].attrs.get("src", "") if d["reduced"] else None, "flipbook": url if flip is not None else None}
    if odd:   # the strip's <source> is one a browser may skip: the picture is not read, and motion:replay says the same
        out.append(_odd_source(case, odd))
        del shown["flipbook"]
    for what, src in shown.items():
        key = "reduced" if what == "reduced" else "strip"
        want_file = project / doc[key]["file"]
        if src is None:
            out.append(f"{case}: no {what} picture in the demo" + (' (an <img class="motion-flip"> in a <picture> whose <source> has a srcset that is a data: URI)' if what == "flipbook" else ""))
            continue
        got = _data_png(src)
        if got is None:
            out.append(f"{case}: the {what} picture is not a base64 data:image/png URI")
        elif not want_file.is_file():
            out.append(f"{case}: {doc[key]['file']} is gone ({older})")
        elif got != want_file.read_bytes():
            out.append(f"{case}: the {what} picture is not {doc[key]['file']} ({older})")
        elif hashlib.sha256(got).hexdigest() != doc[key]["sha256"]:
            out.append(f"{case}: the {what} picture is {doc[key]['file']}, which is not the file frames.json lists (its sha256 differs): run brand-creator frames, then brand-creator book")
    w, h = doc["size"]
    n, scale = len(doc["frames"]), doc["scale"]
    for what, count in (("flipbook", n), ("reduced", 1)):
        png = _data_png(shown[what]) if shown.get(what) else None
        if png and _png_dims(png) != (round(count * w * scale), round(h * scale)):
            warn.append(f"{case}: the {what} picture is {'x'.join(map(str, _png_dims(png) or ()))} px, frames.json says {count} still(s) of "
                        f"{bookdata.num_text(w)} x {bookdata.num_text(h)} px at {bookdata.num_text(scale)}x: run brand-creator frames again")
    if flip is not None:
        st0 = d["states"][(0, 0)]
        if url is not None and abs(density - scale) > 1e-6:
            out.append(f"{case}: the flipbook picture is drawn at {bookdata.num_text(density)}x, frames.json says the stills are {bookdata.num_text(scale)}x, so one still would not fill "
                       f"{bookdata.num_text(w)} x {bookdata.num_text(h)} px: the srcset of its <source> needs the descriptor {bookdata.num_text(scale)}x")
        size, limited = [], []
        for k in ("width", "height"):
            v = _px(_cascade(rules, flip, k, checked=st0) or flip.attrs.get(k))
            for lim, clamp in (("max", min), ("min", max)):   # the size is held under its max- first, and over its min- after: a min- wins where they meet
                raw = (_cascade(rules, flip, f"{lim}-{k}", checked=st0) or "").strip().lower()
                if raw in ("", "none", "auto"):   # the initial values
                    continue
                if _px(raw) is None:
                    out.append(f"{case}: the flipbook's {lim}-{k} is {raw}, which the lint does not read as px: it may show more or less than one still")
                elif v is not None and clamp(v, _px(raw)) != v:
                    v = clamp(v, _px(raw))
                    limited.append(f"{lim}-{k}: {raw}")
            size.append(v)
        (fw, fh), by = size, f" ({', '.join(limited)})" if limited else ""
        if (fw, fh) != (float(w), float(h)):
            out.append(f"{case}: the flipbook is {bookdata.num_text(fw) if fw is not None else 'of no set width'} x {bookdata.num_text(fh) if fh is not None else 'of no set height'} px{by}, "
                       f"one still of frames.json is {bookdata.num_text(w)} x {bookdata.num_text(h)} px" + ("" if limited else f" ({older})"))   # a limit is no old book: rebuilding does not mend it
        fit = (_cascade(rules, flip, "object-fit", checked=st0) or "").strip().lower()
        if fit != "none":
            out.append(f"{case}: the flipbook's object-fit is {fit or 'not set'}; it needs none, so that the strip shows one still at a time")
    return out, warn


def _demo_allowance(text: str):
    """-> a function from the selector of a rule to the durations (ms) the rule may use besides the tokens: for a rule whose selectors match elements of one motion demo
    and of nothing else in the book, that demo's data-length-ms and four times it; for any other rule (a selector that matches nothing, or also something outside the
    demo, or in two demos), none."""
    root = _dom(text)
    demos = _motion_demos(root) if "data-motion-demo" in text else []
    lengths, owner = [], {}   # (length, demo) of each demo that has one; the number of the demo each of its elements lies in
    for d in demos:
        try:
            lengths.append((float(d["fig"].attrs.get("data-length-ms", "")), d))
        except ValueError:
            continue
        owner.update({id(e): len(lengths) - 1 for e in d["els"]})
    every = [e for e in _walk(root) if e.tag != "#root"] if lengths else []
    states = {st for _n, d in lengths for st in d["states"].values()}
    cache: dict[str, list[float]] = {}

    def allowance(where: str) -> list[float]:
        if where not in cache:
            figs, ok = set(), True
            for sel in _split_list(where):
                parts = parse_selector(sel)
                hit = [e for e in every if parts and any(_matches(e, parts, len(parts) - 1, st) for st in states)]
                if not hit or any(id(e) not in owner for e in hit):
                    ok = False
                    break
                figs |= {owner[id(e)] for e in hit}
            n = lengths[next(iter(figs))][0] if ok and len(figs) == 1 else None
            cache[where] = sorted({n, 4 * n}) if n is not None else []
        return cache[where]
    return allowance


def _read_by(prop: str) -> tuple[str, ...]:
    """The motion rows that read a property of the cascade."""
    if prop in ("display", "visibility", "opacity") or prop.startswith(("animation", "transition")):
        return ("motion:reduced", "motion:replay")
    if prop == "object-position":
        return ("motion:replay",)
    return ("motion:stills",) if prop in ("object-fit", "width", "height", "min-width", "max-width", "min-height", "max-height") else ()


def _unread(rules: list[_Rule], demos: list[dict]) -> dict[str, list[str]]:
    """{motion row: ["<selector> (sets display)", ...]}: the rules that set what a row reads (display, visibility, opacity, animation* and transition* for
    motion:reduced and motion:replay; object-position for motion:replay; object-fit, width, height and their min- and max- for motion:stills) under a selector the lint cannot
    evaluate, inside @layer, @scope, @container or @supports ("... inside @layer demo") or holding nested rules ("... with nested rules"), and that could reach an element of a
    demo or an ancestor of one. A layer statement (`@layer a, b;`) is in every row: it orders layers. The cascade the rows read applies none of them: a selector it cannot
    parse, or one with a pseudo-class other than :checked (:is, :not, :where, :has, :hover ...), matches nothing, the at-rules are not evaluated, and a rule that holds nested
    rules is not applied. Each row says which rules it left out."""
    reach = {}
    for d in demos:
        n = d["fig"]
        for e in d["els"]:
            reach[id(e)] = e
        while n is not None and n.tag != "#root":
            reach[id(n)] = n
            n = n.parent
    out: dict[str, list[str]] = {"motion:reduced": [], "motion:replay": [], "motion:stills": []}
    for r in rules:
        if not (_media_holds(r.media, "screen") or _media_holds(r.media, "reduce")):
            continue
        if r.sels and r.sels[0][0].startswith("@layer"):   # a layer statement (style_rules): it orders layers the cascade does not evaluate, so it may change any row
            for row_ in out:
                out[row_].append(f"{r.sels[0][0]} (orders the layers of the cascade)")
            continue
        sets = {}   # row -> what the rule sets that the row reads
        for p, *_rest in r.decls:
            for row_ in _read_by(p):
                sets.setdefault(row_, set()).add(p.split("-")[0] if p.startswith(("animation", "transition")) else p)
        around = _unevaluated(r.media)   # a rule inside @layer, @scope, @container or @supports is not applied, whatever its selector
        for text_, _sp, parts in r.sels:
            if not sets or (parts is not None and not around and not r.nested and not any(ps != "checked" for _c, c in parts for ps in c["pseudos"])):
                continue   # sets nothing a row reads, or a selector the cascade evaluates
            if parts is not None and not any(_matches(e, parts, len(parts) - 1, frozenset(), True) for e in reach.values()):
                continue   # a selector it cannot evaluate, but one that reaches nothing of a demo
            for row_, props in sets.items():
                out[row_].append(f"{_norm_sel(text_)} (sets {', '.join(sorted(props))})" + (f" inside {' and '.join(around)}" if around else "") + (" with nested rules" if r.nested else ""))
    return out


def _note_unread(row_: dict, unread: list[str]) -> None:
    """Say in a row which rules it could not read: a row that would pass is a warning then, never a pass in silence."""
    if unread:
        text = "; ".join(f"not read: {x}" for x in dict.fromkeys(unread[:4])) + (f"; {len(unread) - 4} more" if len(unread) > 4 else "")
        row_["detail"] = f"{row_['detail']}; {text}" if row_["detail"] else text
        if row_["status"] == "pass":
            row_["status"] = "warn"


def _motion_rules(project: Path, text: str, view: dict) -> list[dict]:
    """motion:reduced, motion:replay and motion:stills. A book with nothing for a row to measure gets it as info, never as a pass."""
    rules, kfs, _uris = style_rules(text)
    gaps, moving, stops_unread = _gaps_under_reduced_motion(rules, text)
    demos = _motion_demos(_dom(text)) if "data-motion-demo" in text else []
    red = row("motion:reduced", "pass", "nothing in the book moves under prefers-reduced-motion: reduce")
    rep = row("motion:replay", "info", "every motion demo starts again from its two checkboxes, which the keyboard reaches", "no motion demo")
    sti = row("motion:stills", "info", "every motion demo shows the stills in motion/frames", "no motion demo")
    for d in demos:
        gaps += _reduced_problems(d, rules)
    if gaps:
        red.update(status="fail", detail="; ".join(gaps[:4]) + (f"; {len(gaps) - 4} more" if len(gaps) > 4 else ""))
    elif demos or moving:
        red["detail"] = f"{moving} rule(s) that start an animation or a transition, each switched off" + (f"; {len(demos)} motion demo(s) show their still" if demos else "")
    else:
        red.update(status="info", detail="no motion demo, and no rule that starts an animation or a transition")
    fails, warns = [], []
    if demos:
        frames = {id(d): bookdata.read_frames(project, bookdata.case_folder(d["case"])) for d in demos}
        probs = [p for d in demos for p in _replay_problems(d, rules, kfs, text, frames[id(d)][0])] + (["a @keyframes with no name"] if "" in kfs else [])
        rep.update(status="fail" if probs else "pass", detail="; ".join(probs[:4]) + (f"; {len(probs) - 4} more" if len(probs) > 4 else "") if probs
                   else f"{len(demos)} demo(s): {', '.join(d['case'] for d in demos)}")
        for d in demos:
            f_, w_ = _stills_problems(project, d, rules, *frames[id(d)])
            fails += f_
            warns += w_
    # the stills a generated book has to show and does not: the book was built before `frames` ran (or before the case came into the proof)
    missing = _stills_without_replay(project, view, {d["case"] for d in demos})
    (warns if view.get("mark_source") == "authored-vector" else fails).extend(missing)
    if demos or missing:
        sti.update(status="fail" if fails else "warn" if warns else "pass",
                   detail="; ".join((fails + warns)[:4]) + (f"; {len(fails + warns) - 4} more" if len(fails + warns) > 4 else "") if fails or warns
                   else f"{len(demos)} demo(s): {', '.join(d['case'] for d in demos)}")
    unread = _unread(rules, demos) if demos else {"motion:reduced": [], "motion:replay": [], "motion:stills": []}
    unread["motion:reduced"] = list(dict.fromkeys(unread["motion:reduced"] + stops_unread))   # a stop the cascade does not look at, for a rule that starts motion with no other stop
    for row_, key in ((red, "motion:reduced"), (rep, "motion:replay"), (sti, "motion:stills")):
        _note_unread(row_, unread[key])
    return [red, rep, sti]


def _stills_without_replay(project: Path, view: dict, shown: set[str]) -> list[str]:
    """The cases whose stills the build would make a replay of (a gated proof's, in a motion chapter this book has, with motion not off) and that the book has none of:
    a book built before `frames` ran, or before the case came into the proof."""
    if not bookdata.shows_stills(project, view):
        return []
    how = ("this book is hand-written: add the replay with `brand-creator patch`" if view.get("mark_source") == "authored-vector"
           else "run brand-creator book (the Motion chapter shows the replay through its {{motion}} line)")
    return [f"{doc['case']}: its stills are in {bookdata.FRAMES_DIR}/{folder}/ and the book has no replay of them: {how}" for folder, doc in bookdata.replayable(project)
            if doc["case"] not in shown]


# ---------------------------------------------------------------- reports

def lint_inputs(project: Path, book: Path, view: dict) -> list[Path]:
    """Every file a lint run read: the book, tokens, manifest, facts, config, the FORBIDDEN sources, the mark artwork, whether motion is on (motion/motion.json) and,
    for a book that shows stills, the stills of the gated proofs with their proofs."""
    out = [book]
    for rel in ("assets/tokens/tokens.json", "FACTS.md", "book/book.json", "brief/BRIEF.md", "research/cliches.md", "motion/motion.json"):
        if (project / rel).is_file():
            out.append(project / rel)
    out += bookdata.logo_files(project)
    return out + bookdata.frames_inputs(project, view)


def write_report(project: Path, book: Path, results: list[dict], *, view: dict, **extra) -> "Report":
    """A book-lint Report for `results` (not yet finished; the caller prints and exits with report.finish())."""
    from _common import Report
    rep = Report("book-lint", project, lint_inputs(project, book, view))
    for r in results:
        extra_r = {k: v for k, v in r.items() if k not in ("id", "status", "label")}
        rep.add(r["id"], r["status"], r["label"], **extra_r)
    rep.extra.update(extra)
    rep.extra["manifest_view_sha"] = bookdata.manifest_view_sha(project)
    rep.extra["frames_view_sha"] = bookdata.frames_view_sha(project, view)   # the list of the stills a book can show: `check` sees one that appeared, went or changed
    return rep
