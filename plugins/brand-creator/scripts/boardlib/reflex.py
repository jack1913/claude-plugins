"""The reflex test of a pick board, as data: the reflex line parser, the known pattern names, the grounding words and the judge's list.

A direction's reflex line (data-field="reflex") is one parseable line: `no hits`, or one `hit: <id> | <argument>` per hit, where <id> is an id of
skills/brand-creator/references/ai-defaults.json or an item of the project's research/cliches.md under "Avoid unless argued". `near miss: <id> (<why>)`
records a pattern that looks close but is not one; it is kept and never counted. An optional leading `Reflex test:` label is allowed. `parse` reads
that line and reports what is wrong with it as problems; it never raises on a bad line. Every `hit:` marker gives one Entry, well formed or not, so a
malformed hit is still counted; its problem is reported beside it. `line_rows` and `shared_hit` turn a parsed line into the rows board-lint reports (two fail,
three warn: the format, the ids, and an argument that shares no word with the owner's own material); they live here, not in board_lint.py, so another board
that carries reflex lines reuses them with its own cliché file. `parse_seen` reads the judge's list for a direction; comparing it with the line is board-lint's
business (the rows reflex-seen and reflex-unargued).

The grounding words are a language-neutral floor, not a quality judgement: Unicode letters only, four or more, casefolded, taken from the lines of
FACTS.md and brief/BRIEF.md that are the owner's own (not template lines), minus the words of the templates' own prose. No stop list of any language is
kept.

Standard library only; no clock and no network. The only reads are the named files. This folder is outside scripts/lib/, so a change here does not
make every pack stale.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
AI_DEFAULTS = PLUGIN_ROOT / "skills" / "brand-creator" / "references" / "ai-defaults.json"
TEMPLATES = PLUGIN_ROOT / "templates"
FORMAT = "'no hits', or one 'hit: <id> | <argument>' per hit"   # what a problem tells the author to write
CLICHE_HEADING = "Avoid unless argued"
MIN_WORD = 4   # a content word has at least this many letters
NEXT_RELEASE = "a failure from the next release"   # what every warning of this module ends with
SOURCES = "ai-defaults.json or research/cliches.md"   # where a hit's name may come from, as a message says it
LABELS = {   # the label of each row suffix of line_rows
    "reflex-format": "the reflex line is in the format 'no hits' or 'hit: <id> | <argument>'",
    "reflex-ids": "every hit names a known pattern",
    "reflex-count": "at most one hit per direction",
    "reflex-grounded": "every hit is argued with a word of this brand's own facts or brief",
}

# A marker is not preceded by a letter or '-' (so "white-hit:" and "tophit:" are no markers). The text is white-space collapsed first.
_MARKER = re.compile(r"(?<![^\W\d_])(?<!-)(hit|near[ -]miss):", re.I)
_LABEL = re.compile(r"reflex test\s*:\s*", re.I)
_NO_HITS = re.compile(r"no hits(?![^\W\d_])", re.I)
_NONE_SEEN = re.compile(r"none seen\.?", re.I)
_SEEN_LABEL = re.compile(r"(?:judge saw|seen)\s*:\s*", re.I)
_WORD = re.compile(r"[^\W\d_]+")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_PLACEHOLDER_FIELD = re.compile(r"\{\{[^{}]*\}\}")
_PLACEHOLDER = re.compile(r"\(?\s*(?:\.{3}|…)\s*\)?")
_BULLET = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")


@dataclass(frozen=True)
class Entry:
    """One marker of the line. kind is 'hit' or 'near-miss'. For a hit, name is the id (or the cliché's words) and argument what the author argued;
    for a near miss, name runs to the first '(' and argument is what stands in the parentheses ('' when there are none)."""
    kind: str
    name: str
    argument: str


@dataclass
class Parsed:
    """no_hits: the line says 'no hits'. entries: every marker, in order. problems: what is wrong with the line, one sentence each (empty when it is well formed)."""
    no_hits: bool = False
    entries: list[Entry] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def hits(parsed: Parsed) -> list[Entry]:
    """The entries that count: hits, never near misses."""
    return [e for e in parsed.entries if e.kind == "hit"]


def parse(text: str) -> Parsed:
    """Read one reflex line (see the module docstring). White space is collapsed and a leading 'Reflex test:' dropped.

    No marker: 'no hits' (followed by anything) is no_hits; anything else, free text, is one problem. With markers: the text before the first marker must be
    empty or start with 'no hits'; a hit splits at its first '|' into name and argument (no '|', an empty name or an empty argument is a problem naming the
    entry); a near miss's name runs to the first '(' or to the end; 'no hits' together with a hit is a problem."""
    t = " ".join(text.split())
    label = _LABEL.match(t)
    if label:
        t = t[label.end():]
    out = Parsed()
    marks = list(_MARKER.finditer(t))
    if not marks:
        if _NO_HITS.match(t):
            out.no_hits = True
        elif not t:
            out.problems.append(f"empty: write {FORMAT}")
        else:
            out.problems.append(f"free text: write {FORMAT}")
        return out
    preface = t[:marks[0].start()].strip()
    if _NO_HITS.match(preface):
        out.no_hits = True
    elif preface:
        out.problems.append(f"text before the first marker ('{_clip(preface)}'): start with 'no hits' or a 'hit:' or 'near miss:' marker")
    for i, m in enumerate(marks):
        body = t[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(t)].strip()
        if m.group(1).lower() == "hit":
            out.entries.append(_hit(body, out.problems))
        else:
            out.entries.append(_near_miss(body, out.problems))
    if out.no_hits and hits(out):
        out.problems.append(f"'no hits' together with a hit ({_clip(hits(out)[0].name)}): write {FORMAT}")
    return out


def _clip(s: str, n: int = 60) -> str:
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _hit(body: str, problems: list[str]) -> Entry:
    name, bar, argument = body.partition("|")
    name, argument = name.strip(), argument.strip()
    if not bar:
        problems.append(f"hit '{_clip(name)}' has no '|' and no argument: write 'hit: <id> | <argument>'")
    elif not name:
        problems.append("a hit has no id before the '|': write 'hit: <id> | <argument>'")
    elif not argument:
        problems.append(f"hit '{_clip(name)}' has an empty argument: write 'hit: <id> | <argument>'")
    return Entry("hit", name, argument)


def _near_miss(body: str, problems: list[str]) -> Entry:
    name, paren, rest = body.partition("(")
    name = name.strip().rstrip(".;,").strip()
    argument = ""
    if paren:
        argument = rest.strip().rstrip(".;,").strip()
        argument = argument[:-1].strip() if argument.endswith(")") else argument
    if not name:
        problems.append("a near miss has no id: write 'near miss: <id> (<why>)'")
    return Entry("near-miss", name, argument)


def norm(name: str) -> str:
    """The form names are compared in: casefolded, white space collapsed, one trailing parenthetical dropped
    ('Wheat-adjacent shape (an ear, a sheaf)' and 'wheat-adjacent shape' are the same name)."""
    s = " ".join(name.casefold().split())
    if s.endswith(")"):
        depth = 0
        for i in range(len(s) - 1, -1, -1):
            depth += (s[i] == ")") - (s[i] == "(")
            if depth == 0:
                if s[:i].strip():   # a name that is only a parenthetical stays whole
                    s = s[:i].rstrip()
                break
    return s


def ai_default_ids(path: Path | str | None = None) -> list[str]:
    """The ids of skills/brand-creator/references/ai-defaults.json (the plugin's own copy unless path is given), in file order. A missing or malformed file raises."""
    p = Path(path) if path is not None else AI_DEFAULTS
    items = json.loads(p.read_text(encoding="utf-8")).get("items")
    if not isinstance(items, list) or not all(isinstance(i, dict) and isinstance(i.get("id"), str) for i in items):
        raise ValueError(f"{p}: 'items' must be a list of objects with a string 'id'")
    return [i["id"] for i in items]


def cliche_items(project: Path | str, rel: str = "research/cliches.md") -> list[str]:
    """The bullets under the heading 'Avoid unless argued' of the project's cliché file (rel, project-relative), up to the next heading. Placeholders
    such as '(...)' and HTML comments are dropped; [] when the file is missing. The site board passes rel='research/site-cliches.md'."""
    f = Path(project) / rel
    if not f.is_file():
        return []
    items: list[str] = []
    in_section = False
    for line in _COMMENT.sub("", f.read_text(encoding="utf-8")).splitlines():
        h = _HEADING.match(line)
        if h:
            in_section = h.group(1).strip().casefold().startswith(CLICHE_HEADING.casefold())
            continue
        b = _BULLET.match(line)
        if in_section and b:
            item = b.group(1).strip()
            if item and not _PLACEHOLDER.fullmatch(item) and item not in items:
                items.append(item)
    return items


def known(name: str, ids: list[str], cliches: list[str]) -> str | None:
    """Where a hit's name comes from: 'ai-defaults' (an id), 'cliches' (an item of the cliché file) or None (neither). Compared by norm."""
    n = norm(name)
    if not n:
        return None
    if n in {norm(i) for i in ids}:
        return "ai-defaults"
    if n in {norm(c) for c in cliches}:
        return "cliches"
    return None


def line_rows(parsed: Parsed, ids: list[str], cliches: list[str], ground: set[str] | None = None,
              sources: str = SOURCES) -> list[tuple[str, str, str]]:
    """The rows one reflex line earns, as (suffix, status, detail), in this order:

    reflex-format    warn when the line has parse problems (quoted, with the format); pass otherwise.
    reflex-ids       warn when a hit names neither an id (ids) nor an item of the cliché file (cliches); the detail names them and says where a name may
                     come from (`sources`, so the caller can say that the project has no cliché file). Pass otherwise.
    reflex-count     fail on two or more hits in one direction ("replace a part before showing it"); pass otherwise. Near misses are not hits.
    reflex-grounded  only when `ground` is given (the words of `ground_words`; None skips the row) and a hit has an argument: warn when the argument of a hit
                     shares no content word with `ground` (the detail names the hit and asks for the fact, place or craft that earns it); pass otherwise,
                     naming the shared words. An empty `ground` (FACTS.md and brief/BRIEF.md missing, or still the templates) checks nothing: a warning that says
                     "NOT verified". No row for a line with no hit, or whose hits have no argument (the format row reports those).

    A warning says "a failure from the next release". A hit that has no name is the format row's business, not the ids row's."""
    rows: list[tuple[str, str, str]] = []
    if parsed.problems:
        said = "; ".join(parsed.problems)
        rows.append(("reflex-format", "warn", f"{said}{'' if FORMAT in said else f' (the format: {FORMAT})'}; a warning now, {NEXT_RELEASE}"))
    else:
        rows.append(("reflex-format", "pass", "no hits" if parsed.no_hits and not parsed.entries else f"{len(hits(parsed))} hit(s), {len(parsed.entries) - len(hits(parsed))} near miss(es)"))
    named = [e for e in hits(parsed) if norm(e.name)]
    unknown = [e.name for e in named if known(e.name, ids, cliches) is None]
    if unknown:
        rows.append(("reflex-ids", "warn", f"names no known pattern: {', '.join(repr(n) for n in unknown)}. A hit names an id or item of {sources}; a warning now, {NEXT_RELEASE}"))
    else:
        rows.append(("reflex-ids", "pass", ", ".join(f"{e.name} ({known(e.name, ids, cliches)})" for e in named) or "no hit to name"))
    n = len(hits(parsed))
    if n >= 2:
        rows.append(("reflex-count", "fail", f"{n} hits in one direction ({', '.join(e.name or '?' for e in hits(parsed))}): replace a part before showing it, so that at most one pattern is left to argue"))
    else:
        rows.append(("reflex-count", "pass", f"{n} hit(s)"))
    if ground is not None:
        grounded = _grounded_row(parsed, ground)
        if grounded:
            rows.append(grounded)
    return rows


def _grounded_row(parsed: Parsed, ground: set[str]) -> tuple[str, str, str] | None:
    """The reflex-grounded row of line_rows (see there), or None when no hit has an argument to check."""
    argued = [e for e in hits(parsed) if e.argument.strip()]
    if not argued:
        return None
    if not ground:
        return ("reflex-grounded", "warn",
                f"NOT verified: FACTS.md and brief/BRIEF.md hold no words of the owner's own (missing, or still the template), so the argument of "
                f"{', '.join(repr(e.name or '?') for e in argued)} was checked against nothing. Fill them in, then name the fact, place or craft that earns the hit; "
                f"a warning now, {NEXT_RELEASE}")
    shared = [(e, sorted(content_words(e.argument) & ground)) for e in argued]
    ungrounded = [e.name or "?" for e, words in shared if not words]
    if ungrounded:
        return ("reflex-grounded", "warn",
                f"the argument of {', '.join(repr(n) for n in ungrounded)} shares no word with FACTS.md or brief/BRIEF.md: name the fact, place or craft of this brand "
                f"that earns it; a warning now, {NEXT_RELEASE}")
    return ("reflex-grounded", "pass", "; ".join(f"{e.name or '?'} shares {', '.join(words)}" for e, words in shared))


def shared_hit(parsed_list: list[Parsed]) -> str | None:
    """The name (in norm form) that every line hits, when there are two or more lines; None otherwise. If the lines share several, the first of the first line's
    hits is returned. A line with no hit makes the answer None."""
    if len(parsed_list) < 2:
        return None
    common = [norm(e.name) for e in hits(parsed_list[0]) if norm(e.name)]
    for p in parsed_list[1:]:
        names = {norm(e.name) for e in hits(p)}
        common = [c for c in common if c in names]
    return common[0] if common else None


def content_words(text: str) -> set[str]:
    """The words an argument is grounded with: runs of Unicode letters (no digits, no '_'), casefolded, four letters or more. Text is put in NFC
    first, so a letter typed as base letter plus accent is not split."""
    return {w for w in _WORD.findall(unicodedata.normalize("NFC", text).casefold()) if len(w) >= MIN_WORD}


def _lines(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]


def _template_pattern(line: str) -> re.Pattern[str] | None:
    """The pattern that matches a template line once its {{...}} placeholders are filled (the title line '# {{name}}: facts' is '# Acme Tools: facts' in a
    project); None for a line with no placeholder, which is only ever matched verbatim."""
    parts = _PLACEHOLDER_FIELD.split(line)
    if len(parts) == 1:
        return None
    return re.compile(".+?".join(re.escape(p) for p in parts))


def ground_words(project: Path | str) -> set[str]:
    """The content words of the owner's own material: the lines of FACTS.md and brief/BRIEF.md that are not lines of the plugin's templates/FACTS.md and
    templates/BRIEF.md (stripped, verbatim; a template line with a {{...}} placeholder, such as the title, also matches with the placeholder filled in, so
    the brand's name in the title is no ground word), minus the content words of those templates' lines that do not start with '|' (their prose). A missing
    project file adds nothing; a missing template raises."""
    template_lines: set[str] = set()
    template_patterns: list[re.Pattern[str]] = []
    prose: set[str] = set()
    for name in ("FACTS.md", "BRIEF.md"):
        for ln in _lines(TEMPLATES / name):
            template_lines.add(ln)
            pattern = _template_pattern(ln)
            if pattern:
                template_patterns.append(pattern)
            if not ln.startswith("|"):
                prose |= content_words(ln)
    words: set[str] = set()
    for rel in ("FACTS.md", "brief/BRIEF.md"):
        f = Path(project) / rel
        if f.is_file():
            for ln in _lines(f):
                if ln not in template_lines and not any(p.fullmatch(ln) for p in template_patterns):
                    words |= content_words(ln)
    return words - prose


def _seen_items(node_texts: list[str]) -> list[str]:
    texts = [" ".join(t.split()) for t in node_texts]
    if len(texts) == 1:
        label = _SEEN_LABEL.match(texts[0])
        texts = (texts[0][label.end():] if label else texts[0]).split(";")
    items = [t.strip().rstrip(".;,").strip() for t in texts]
    return [i for i in items if i]


def parse_seen(node_texts: list[str]) -> list[str]:
    """The judge's list for one direction. Several texts are the items themselves (the list's li elements). One text is either 'none seen' (an empty
    list) or items split at ';' after an optional 'judge saw:' or 'seen:' label. Items are trimmed of white space and trailing '.', ';' and ','; an
    empty item and a 'none seen' item are dropped."""
    return [i for i in _seen_items(node_texts) if not _NONE_SEEN.fullmatch(i)]


def says_none_seen(node_texts: list[str]) -> bool:
    """Whether the judge's list (the texts `parse_seen` reads) says 'none seen' in so many words. A list that is only its label ('judge saw:') or empty
    is no answer: `parse_seen` gives [] for it as it does for 'none seen', and this tells the two apart."""
    return any(_NONE_SEEN.fullmatch(i) for i in _seen_items(node_texts))
