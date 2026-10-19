"""The Markdown subset of the brand book's chapter files (book/chapters/*.md) and its HTML output. Standard library only.

Documented subset (anything else is an error with the line number, never a silent guess):

  # Title                   optional first line: the chapter's title (the registry's default title is used without it)
  ## Heading / ### Heading  h3 / h4 (the chapter title is the h2; deeper headings are not in the subset)
  paragraphs                lines up to a blank line are joined
  - item / * item           flat bullet list (nesting is not in the subset); - [ ] item / - [x] item is a task list
  1. item                   flat numbered list
  > quote                   blockquote (one paragraph per run of lines)
  | a | b |                 pipe table: header row, a |---|---| row, body rows
  ```                       fenced code
  ![alt](path)              an image on its own line: a file inside the project, embedded as a data URI
  ::: variant G NAME ... ::: / ::: switcher G ... :::
                            choice scaffolding while a decision is open; `brand-creator collapse` removes what lost
  {{name}} / {{name:arg}}   computed blocks on their own line (see book.py) and computed inline values: {{count:files}},
                            {{fact:label}}, {{edition}}, {{name}}, {{approved}}
  inline                    **bold**, *italic* or _italic_, `code`, [text](#anchor), [text](relative/file), [text](mailto:...)

Raw HTML is escaped, so a chapter can never carry a script or a network reference by accident. `[[fill: ...]]` markers left in a
chapter are an error. Links with an http(s) address are written as given: book_lint fails them (a book makes no network calls).
"""
from __future__ import annotations

import html
import re


class MdError(ValueError):
    def __init__(self, line: int, message: str):
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


def esc(s: str) -> str:
    return html.escape(s, quote=True)


_CODE = re.compile(r"`([^`\n]+)`")
_DIRECTIVE = re.compile(r"\{\{([a-z][a-z0-9-]*)(?::([^{}]*))?\}\}")
_LINK = re.compile(r"\[([^\[\]]+)\]\(([^()\s]+)\)")
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_EM_STAR = re.compile(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])")
_EM_UND = re.compile(r"(?<![\w_])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w_])")
_PATTERNS = [("code", _CODE), ("directive", _DIRECTIVE), ("link", _LINK), ("bold", _BOLD), ("em", _EM_STAR), ("em", _EM_UND)]
_FILL = re.compile(r"\[\[fill\b")
_SAFE_URL = re.compile(r"^(#[^\s]*|mailto:[^\s]+|https?://[^\s]+|[^:\s]+)$", re.I)


def inline(text: str, ctx, lang: str, line: int) -> str:
    """Inline Markdown to HTML. ctx.inline(name, arg, lang) renders {{name:arg}}."""
    out: list[str] = []
    pos = 0
    while pos < len(text):
        best = None
        for kind, rx in _PATTERNS:
            m = rx.search(text, pos)
            if m and (best is None or m.start() < best[1].start()):
                best = (kind, m)
        if best is None:
            out.append(esc(text[pos:]))
            break
        kind, m = best
        out.append(esc(text[pos:m.start()]))
        if kind == "code":
            out.append(f"<code>{esc(m.group(1))}</code>")
        elif kind == "directive":
            name, arg = m.group(1), (m.group(2) or "").strip()
            if name not in ctx.INLINE:
                hint = " (it is a block: put it on a line of its own)" if name in ctx.BLOCK else ""
                raise MdError(line, f"unknown inline value {{{{{name}}}}}{hint}; inline values are {', '.join(sorted(ctx.INLINE))}")
            out.append(ctx.inline(name, arg, lang))
        elif kind == "link":
            url = m.group(2)
            if re.match(r"(?i)(javascript|data|vbscript):", url) or not _SAFE_URL.match(url):
                raise MdError(line, f"link target {url!r} is not allowed (use #anchor, a relative file, mailto: or an address)")
            out.append(f'<a href="{esc(url)}">{inline(m.group(1), ctx, lang, line)}</a>')
        elif kind == "bold":
            out.append(f"<strong>{inline(m.group(1), ctx, lang, line)}</strong>")
        else:
            out.append(f"<em>{inline(m.group(1), ctx, lang, line)}</em>")
        pos = m.end()
    return "".join(out)


def _split_row(ln: str) -> list[str]:
    s = ln.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


_DELIM = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_BULLET = re.compile(r"^([-*])\s+(.*)$")
_TASK = re.compile(r"^\[( |x|X)\]\s+(.*)$")
_ORDERED = re.compile(r"^(\d+)[.)]\s+(.*)$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^:::\s*(variant|switcher)\s+(.*?)\s*$")
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^()\s]+)\)\s*$")


def convert(text: str, ctx, lang: str) -> tuple[str | None, str]:
    """-> (title or None, body HTML). ctx supplies BLOCK, INLINE (name sets), block(name, arg, lang), inline(name, arg, lang),
    image(path, alt, lang) and variant(kind, group, name, line)."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for i, ln in enumerate(lines, 1):
        if _FILL.search(ln):
            raise MdError(i, f"unfilled marker {ln.strip()[:70]!r}: write the content, then build again")
        if "\t" in ln.lstrip("\t") and ln.startswith("\t"):
            raise MdError(i, "tab-indented lines (nested blocks) are not in the Markdown subset")
    title = None
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines):
        m = _HEADING.match(lines[i])
        if m and len(m.group(1)) == 1:
            title = m.group(2).strip()
            i += 1
    body, _end, _closed = _blocks(lines, i, ctx, lang, in_fence=False)
    return title, "\n".join(body)


def _blocks(lines: list[str], i: int, ctx, lang: str, in_fence: bool) -> tuple[list[str], int, bool]:
    """-> (html blocks, index after them, whether a closing ::: ended the run)"""
    out: list[str] = []
    n = len(lines)
    para: list[tuple[int, str]] = []

    def flush():
        if para:
            first = para[0][0]
            out.append("<p>" + inline(" ".join(t.strip() for _, t in para), ctx, lang, first) + "</p>")
            para.clear()

    while i < n:
        ln = lines[i]
        s = ln.strip()
        ln_no = i + 1
        if not s:
            flush()
            i += 1
            continue
        if s == ":::":
            flush()
            if in_fence:
                return out, i + 1, True
            raise MdError(ln_no, "a closing ::: with no open ::: variant / ::: switcher")
        fm = _FENCE.match(s)
        if fm:
            flush()
            kind, rest = fm.group(1), fm.group(2).split()
            if (kind == "variant" and len(rest) != 2) or (kind == "switcher" and len(rest) != 1) or not all(_NAME.match(x) for x in rest):
                raise MdError(ln_no, f"use `::: variant GROUP NAME` or `::: switcher GROUP` (lowercase words, digits, hyphens), got {s!r}")
            group, name = rest[0], (rest[1] if kind == "variant" else "")
            ctx.variant(kind, group, name, ln_no)
            inner, i, closed = _blocks(lines, i + 1, ctx, lang, in_fence=True)
            if not closed:
                raise MdError(ln_no, f"the ::: {kind} {group} block is never closed with :::")
            attr = f'data-variant="{esc(group)}:{esc(name)}"' if kind == "variant" else f'data-switcher="{esc(group)}"'
            out.append(f'<div class="{kind}" {attr}>\n' + "\n".join(inner) + "\n</div>")
            continue
        if s.startswith("```"):
            flush()
            j = i + 1
            code = []
            while j < n and not lines[j].strip().startswith("```"):
                code.append(lines[j])
                j += 1
            if j >= n:
                raise MdError(ln_no, "a ``` code fence is never closed")
            out.append("<pre><code>" + esc("\n".join(code)) + "</code></pre>")
            i = j + 1
            continue
        dm = _DIRECTIVE.fullmatch(s)
        if dm:
            flush()
            name, arg = dm.group(1), (dm.group(2) or "").strip()
            if name in ctx.BLOCK:
                out.append(ctx.block(name, arg, lang))
            elif name in ctx.INLINE:
                out.append("<p>" + ctx.inline(name, arg, lang) + "</p>")
            else:
                raise MdError(ln_no, f"unknown block {{{{{name}}}}}; blocks are {', '.join(sorted(ctx.BLOCK))}")
            i += 1
            continue
        im = _IMAGE.match(s)
        if im:
            flush()
            out.append(ctx.image(im.group(2), im.group(1), lang, ln_no))
            i += 1
            continue
        hm = _HEADING.match(s)
        if hm:
            flush()
            lvl = len(hm.group(1))
            if lvl == 1:
                raise MdError(ln_no, "a `# Title` line is only allowed as the first line of the file")
            if lvl > 3:
                raise MdError(ln_no, "headings deeper than ### are not in the Markdown subset")
            tag = "h3" if lvl == 2 else "h4"
            out.append(f"<{tag}>{inline(hm.group(2), ctx, lang, ln_no)}</{tag}>")
            i += 1
            continue
        if s.startswith("|") and i + 1 < n and _DELIM.match(lines[i + 1]):
            flush()
            head = _split_row(s)
            j = i + 2
            rows = []
            while j < n and lines[j].strip().startswith("|"):
                row = _split_row(lines[j])
                if len(row) != len(head):
                    raise MdError(j + 1, f"table row has {len(row)} cells, the header has {len(head)}")
                rows.append(row)
                j += 1
            th = "".join(f"<th>{inline(c, ctx, lang, ln_no)}</th>" for c in head)
            tr = "".join("<tr>" + "".join(f"<td>{inline(c, ctx, lang, j0 + i + 3)}</td>" for c in r) + "</tr>" for j0, r in enumerate(rows))
            out.append(f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>')
            i = j
            continue
        if s.startswith(">"):
            flush()
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote><p>" + inline(" ".join(quote), ctx, lang, ln_no) + "</p></blockquote>")
            continue
        bm = _BULLET.match(ln) if not ln.startswith((" ", "\t")) else None
        om = _ORDERED.match(ln) if not ln.startswith((" ", "\t")) else None
        if bm or om:
            flush()
            ordered = om is not None
            items = []
            while i < n and lines[i].strip():
                cur = lines[i]
                if cur.startswith((" ", "\t")):
                    if _BULLET.match(cur.strip()) or _ORDERED.match(cur.strip()):
                        raise MdError(i + 1, "nested lists are not in the Markdown subset")
                    items[-1][1].append(cur.strip())   # a wrapped item line
                    i += 1
                    continue
                m2 = (_ORDERED if ordered else _BULLET).match(cur)
                if not m2:
                    break
                items.append((i + 1, [m2.group(2 if not ordered else 2)]))
                i += 1
            lis = []
            for ln0, parts in items:
                t = " ".join(parts)
                tm = _TASK.match(t) if not ordered else None
                if tm:
                    done = tm.group(1) != " "
                    lis.append(f'<li class="task" data-task="{"done" if done else "open"}">{inline(tm.group(2), ctx, lang, ln0)}</li>')
                else:
                    lis.append(f"<li>{inline(t, ctx, lang, ln0)}</li>")
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(lis) + f"</{tag}>")
            continue
        para.append((ln_no, ln))
        i += 1
    flush()
    return out, i, False
