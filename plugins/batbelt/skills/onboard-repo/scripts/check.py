#!/usr/bin/env python3
"""The standing grounding gates: `check-docs`, `check-instructions`, `redact`.

Split out of onboard.py so the skills that run for YEARS do not have to carry the
one-shot onboarding machinery they must never run (ADR-0008). onboard-repo stamps
THIS file -- and only this file -- beside `update-docs` and `update-rules`, so a
maintained repo gets ~1.4k lines instead of the ~3.4k onboard.py/onboard_lib.py pair,
and a skill named `update-rules` no longer ships a script named `onboard.py`.

Stdlib only, and it imports NOTHING from this package -- the dependency points one
way (onboard.py and onboard_lib.py import from here, never the reverse). That is
what makes a plain `cp` of this single file sound, and a test pins it.

Usage:
  check.py check-docs <roots...> [--captures DIR] [--coverage FILE] [--forbidden a,b]
                                 [--only PATH]... [--no-tier-check]
  check.py check-instructions <roots...> [--repo-root DIR]...
  check.py redact <raw_file> --home H --user U --stamp S [--extra a,b]

Both checkers print SEVERITY\tCODE\tfile:lineno\tdetail to stdout, exit 1 on an
error-level finding, 0 for warnings or a clean tree, and 2 on bad args -- never a
traceback.
"""

import json
import pathlib
import re
import sys

_REDACT_USAGE = "usage: check.py redact <raw_file> --home H --user U --stamp S [--extra a,b]"


_USAGE_PREFIX = "usage: check.py"

# Sentinel for "argv ended where a flag's value should be". `next(it, "")` silently
# supplied a default instead, so a value-taking flag in last position became a no-op:
# `--forbidden` at the end scanned for nothing and exited 0 on a tree containing the
# token it was asked to find. A flag that quietly does nothing is the failure mode this
# whole module exists to eliminate, so a missing value is now a usage error.
_MISSING = object()


def _usage(msg, prog="check.py"):
    """Bad args -> stderr + exit 2. `prog` lets onboard.py delegate here without
    printing a usage line naming a file the operator did not run.

    The rewrite is anchored to the `usage: ` prefix, NOT a blanket substring replace.
    Most messages through here are `ERROR: not found: <path>` carrying a path the
    operator typed, and a bare replace edited that path: `check-instructions
    /nope/scripts/check.py` reported `/nope/scripts/onboard.py` -- a file that appears
    nowhere in the command, sending them to the wrong place while debugging. Renaming
    the program in its own usage line is the only substitution that is ever right.
    """
    if msg.startswith(_USAGE_PREFIX):
        msg = "usage: " + prog + msg[len(_USAGE_PREFIX) :]
    sys.stderr.write(msg + "\n")
    return 2


# --- markdown/text primitives (shared by both gates) ---------------------------
# A fenced code block: a ``` or ~~~ run to its closer (the same marker, 0-3 spaces
# of indent), OR — for an UNCLOSED opener — to end of text (CommonMark). A backtick
# opener's line may not contain another backtick (else it's an inline code span, not
# a fence — review M1). The closer tolerates a trailing CR so CRLF files still close
# (review C2).
_FENCE_RE = re.compile(
    r"(?ms)^[ \t]*(?:(`{3,})(?![^\n`]*`)|(~{3,})).*?(?:^[ \t]{0,3}(?:\1|\2)[ \t]*\r?$|\Z)"
)
_ATX_RE = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$", re.MULTILINE)
_DELIM_CELL_RE = re.compile(r"^:?-+:?$")


def _split_fences(text):
    """Yield (segment, is_fence) chunks so callers can transform only prose."""
    pos = 0
    for m in _FENCE_RE.finditer(text):
        if m.start() > pos:
            yield text[pos : m.start()], False
        yield m.group(0), True
        pos = m.end()
    if pos < len(text):
        yield text[pos:], False


# Same shape as _INLINE_LINK_RE (defined below, deliberately duplicated rather than
# reordered) but with the leading '!' captured: GitHub slugs the RENDERED heading, so
# a link contributes its display text and an image contributes nothing at all (an
# <img> element has no text content). Slugging the raw source instead folds the link
# TARGET into the anchor -- `## A [b](c/d.md)` became `a-bcdmd` -- which is the single
# largest source of false BROKEN_ANCHOR reports on any repo whose headings link out.
_SLUG_INLINE_RE = re.compile(r"(!?)\[([^\]\n]*)\]\(\s*(?:<[^>]*>|[^)\s]+)?(?:\s+\"[^\"]*\")?\s*\)")


def _render_inline(s):
    """Reduce a heading's inline markdown to the text content GitHub renders.
    Links keep their display text, images contribute none. Backticks, '*' and '~'
    need no handling here -- _base_slug's character filter already drops them."""
    return _SLUG_INLINE_RE.sub(lambda m: "" if m.group(1) else m.group(2), s)


def _base_slug(s):
    """github-slugger base: render inline markdown, lowercase, drop
    non-[word/-/space], spaces -> '-'. Keeps '_' and Unicode word chars
    (re.UNICODE default). No run-collapsing."""
    s = _render_inline(s).lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def heading_slugs(text):
    """ATX-heading slugs in document order with github-slugger collision dedup:
    every emitted slug is recorded; a repeat bumps '-N' until free
    (verified: dup,dup-1,dup -> dup,dup-1,dup-2 ; dup,dup,dup-1 ->
    dup,dup-1,dup-1-1). Fenced '#'-lines are skipped. Setext headings,
    NFD-combining-mark headings and underscore emphasis (`## _x_` renders as
    `x` on GitHub, slugs as `_x_` here) are documented non-parses (spec 4.1)."""
    occ = {}
    out = []
    for seg, is_fence in _split_fences(text):
        if is_fence:
            continue
        for m in _ATX_RE.finditer(seg):
            content = m.group(2).strip().rstrip("#").strip()
            base = _base_slug(content)
            result = base
            while result in occ:
                occ[base] = occ.get(base, 0) + 1
                result = "%s-%d" % (base, occ[base])
            occ[result] = 0
            out.append(result)
    return out


def heading_texts(text):
    """ATX-heading TEXT in document order, at any level, fenced '#'-lines skipped.

    Shares `heading_slugs`' parse so "is there a Context section?" is answered by the
    same notion of a heading the anchor checker uses. A bare `"## Context" in text`
    substring test answered it two ways wrong: `### Context` is the same section at a
    different depth (false positive on the miss), and a `## Decision` line quoted
    inside a fence is not a section at all (false negative on the hit).
    """
    out = []
    for seg, is_fence in _split_fences(text):
        if is_fence:
            continue
        for m in _ATX_RE.finditer(seg):
            out.append(_render_inline(m.group(2).strip().rstrip("#").strip()))
    return out


def _split_table_row(row):
    """Split a table row on UNESCAPED '|', dropping one outer empty cell each
    side (leading/trailing pipe). '\\|' does not split."""
    cells = re.split(r"(?<!\\)\|", row)
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return cells


def _is_delim_row(cells):
    return len(cells) > 0 and all(_DELIM_CELL_RE.match(c.strip()) for c in cells)


def _fenced_line_numbers(text):
    """Set of 1-based line numbers that fall inside a fenced code block."""
    fenced = set()
    base_line = 0  # newlines in text BEFORE the current segment (incremental, O(n))
    for seg, is_fence in _split_fences(text):
        if is_fence:
            start = base_line + 1
            for k in range(seg.count("\n") + 1):
                fenced.add(start + k)
        base_line += seg.count("\n")
    return fenced


def table_cell_errors(text):
    """Lint GFM pipe tables. A table = a header row + a delimiter row (each cell,
    stripped, matches ':?-+:?') with the header's cell count, then body rows to a
    blank/non-row line. Rows split on unescaped '|'. Returns (lineno, kind, got,
    want): 'error' when a body row has MORE cells than the header (an unescaped
    pipe inside a code span corrupts the row — micromark-verified), 'warn' when
    fewer. Fenced lines are ignored (spec 4.1)."""
    fenced = _fenced_line_numbers(text)
    lines = text.split("\n")
    errors = []
    i = 0
    while i < len(lines):
        ln = i + 1
        if ln in fenced or "|" not in lines[i] or i + 1 >= len(lines):
            i += 1
            continue
        hdr = _split_table_row(lines[i])
        dcells = _split_table_row(lines[i + 1])
        if (i + 2) in fenced or not _is_delim_row(dcells) or len(dcells) != len(hdr):
            i += 1
            continue
        want = len(hdr)
        j = i + 2
        while j < len(lines) and (j + 1) not in fenced and lines[j].strip() and "|" in lines[j]:
            got = len(_split_table_row(lines[j]))
            if got > want:
                errors.append((j + 1, "error", got, want))
            elif got < want:
                errors.append((j + 1, "warn", got, want))
            j += 1
        i = j if j > i else i + 1
    return errors


# inline link/image: [disp](target)  target = <angle w/ spaces> | bare-no-space,
# with optional "title" and trailing ws before ')'. The display group forbids a
# newline (`[^\]\n]*`) so an UNCLOSED `[` cannot make the engine rescan across
# blank lines — link display text never spans a line for our purposes, and this
# bounds the backtracking window to a single line (review S2-M-DoS).
_INLINE_LINK_RE = re.compile(r"!?\[([^\]\n]*)\]\(\s*(?:<([^>]*)>|([^)\s]+))(?:\s+\"[^\"]*\")?\s*\)")
# reference definition:  [label]: target   (line-anchored)
_REFDEF_LINK_RE = re.compile(r"(?m)^\s*\[([^\]]+)\]:\s*(?:<([^>]*)>|(\S+))")

# An INLINE CODE SPAN: a backtick run closed by a run of the same length, not crossing a
# newline. A link inside one is TYPESET, not followed -- so it names no target and cannot
# be broken. Skipping fences alone was not enough: a doc that writes ABOUT a link, which
# any page documenting this gate has to, earned an error-level BROKEN_LINK for a file it
# never claimed exists. An unclosed or multi-line run is left alone (it is not a span).
_CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(?:[^`\n]|(?!\1)`+)+?\1(?!`)")


def _mask_code_spans(seg):
    """Blank out inline code spans, preserving length so line numbers stay exact."""
    return _CODE_SPAN_RE.sub(lambda m: " " * len(m.group(0)), seg)


def iter_markdown_links(text):
    """Yield (display, target, lineno) for inline links, images, and reference
    definitions over non-fence lines, EXCLUDING inline code spans. Angle targets
    (`<my file.md>`) are captured whole. HTML <a>/<img> are not parsed (documented,
    spec 4.1)."""
    out = []
    base_line = 0  # newlines in text BEFORE the current segment (incremental, O(n))
    for seg, is_fence in _split_fences(text):
        if not is_fence:
            seg = _mask_code_spans(seg)
            for rx, disp_i, ang_i, bare_i in (
                (_INLINE_LINK_RE, 1, 2, 3),
                (_REFDEF_LINK_RE, 1, 2, 3),
            ):
                # finditer yields matches in increasing start(); advance a running
                # (pos, nl) cursor instead of re-slicing seg[:m.start()] per match.
                pos = 0
                nl = 0  # newlines in seg[:pos]
                for m in rx.finditer(seg):
                    nl += seg[pos : m.start()].count("\n")
                    pos = m.start()
                    target = m.group(ang_i) if m.group(ang_i) is not None else m.group(bare_i)
                    out.append((m.group(disp_i), target, base_line + nl + 1))
        base_line += seg.count("\n")
    out.sort(key=lambda t: t[2])
    return out


_ELISION = ("…", "# ...", "# …", "...")


def redact_output(text, home, user, stamp, extra_tokens):
    """Best-effort redaction of the SUPPLIED tokens (home/user/stamp/extra),
    boundary-anchored and env-parameterized — never a bare substring. This is
    NOT a secret scanner: it removes only what it is told, so AWS keys,
    `ghp_`/`sk-` tokens, `user:pass@` URLs, and emails pass straight through.
    The caller MUST review the output for any other secrets before committing it."""
    out = text
    if home:
        # One case-insensitive boundary rule: `/home/jack/proj` -> `~/proj` (the
        # trailing `/` is a lookahead, preserved), `/home/jack` before end or
        # punctuation -> `~`, while `/home/jackson` is left alone (`s` is a word
        # char). Case-insensitive so `/USERS/JACK` still redacts on a
        # case-insensitive FS (review S2-L-redact-home).
        out = re.sub(re.escape(home) + r"(?![\w])", "~", out, flags=re.IGNORECASE)
    if user:
        out = re.sub(r"(?<![\w-])" + re.escape(user) + r"(?![\w-])", "<user>", out)
    if stamp:
        out = re.sub(r"(?<![\w-])" + re.escape(stamp) + r"(?![\w-])", "<stamp>", out)
    for tok in extra_tokens or ():
        if tok:
            out = re.sub(r"(?<![\w-])" + re.escape(tok) + r"(?![\w-])", "<redacted>", out)
    return out


def canonicalize_output(text):
    """Check-time, env-free normalization: newlines -> \\n, strip trailing ws per
    line, drop trailing blank lines, end with exactly one newline. Idempotent
    (spec 4.1)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    while len(lines) > 1 and lines[-1] == "":
        lines.pop()
    if lines == [""]:
        return ""
    return "\n".join(lines) + "\n"


def output_subsequence_ok(shown, committed):
    """True iff every non-elision line of canonicalize_output(shown) appears, in
    order, within canonicalize_output(committed); an elision token consumes >=1
    committed lines (spec 4.1)."""
    s = [ln for ln in canonicalize_output(shown).split("\n")]
    c = canonicalize_output(committed).split("\n")
    ci = 0
    for line in s:
        if line.strip() in _ELISION:
            # consume at least one committed line
            if ci >= len(c):
                return False
            ci += 1
            continue
        if line == "":
            continue
        while ci < len(c) and c[ci] != line:
            ci += 1
        if ci >= len(c):
            return False
        ci += 1
    return True


_FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[ \t]*(.*?)[ \t]*\r?$")
_FENCE_CLOSE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[ \t]*\r?$")


def iter_fenced_blocks(text):
    """Yield (info_string, body, start_lineno) for each fenced block. info_string
    is the opener line after the backtick/tilde run (e.g. 'text capture=x'); body
    excludes the fence lines; start_lineno is 1-based at the opener."""
    out = []
    base_line = 0  # newlines in text BEFORE the current segment (incremental, O(n))
    for seg, is_fence in _split_fences(text):
        if is_fence:
            start = base_line + 1
            lines = seg.split("\n")
            m = _FENCE_OPEN_RE.match(lines[0])
            info = m.group(2) if m else ""
            body_lines = lines[1:]
            if body_lines and _FENCE_CLOSE_RE.match(body_lines[-1]):
                body_lines = body_lines[:-1]  # drop the real close-fence line
            elif body_lines and body_lines[-1] == "":
                # UNCLOSED fence to EOF: the opener's own trailing '\n' left a
                # phantom "" line that is NOT a close-fence — drop it so the body
                # is honest (review S2-M1), not padded with a spurious blank.
                body_lines = body_lines[:-1]
            out.append((info, "\n".join(body_lines) + ("\n" if body_lines else ""), start))
        base_line += seg.count("\n")
    return out


# --- Grounding claims in rules and skills ------------------------------------
#
# Instruction files rot differently from docs: a count drifts on every merge and a
# cited symbol gets renamed out from under the file. An agent then acts on the
# stale claim, which is worse than having no rule at all. These extractors are
# deliberately narrow -- a checker that cries wolf gets ignored, and this repo has
# already shipped one over-eager grounding rule (see CHANGELOG 0.2.16).

# A backticked `path:line` citation. The path must look like a path (a slash or a
# dot-extension) and must not carry glob or call syntax, which is what keeps
# `Bash(git log:*)`, `**/*.cs` and `https://host:443` out of the results.
_CITATION_RE = re.compile(r"`([A-Za-z0-9_./\-]+\.[A-Za-z0-9]+):(\d+)(?:-\d+)?`")

# Nouns that make a bare number a checkable claim about the codebase rather than
# prose. "3 rounds" or "two tiers" are not claims about what is in the repo.
_COUNT_NOUNS = (
    "files",
    "modules",
    "members",
    "projects",
    "sites",
    "call sites",
    "callers",
    "occurrences",
    "entries",
    "rules",
    "skills",
    "packages",
    "tests",
    "classes",
    "interfaces",
    "migrations",
)
# The `(?<![\w.§#])` guard sits immediately before the digit so the number must start a
# token. Without it the digit was plucked out of the middle of an identifier or a
# version: "k6 stress tests" read as (6, tests) and "PHP 8.4 classes" as (4, classes),
# both unfixable by the author because there is no number there to ground.
#
# `§` and `#` are in the class for the same reason, found by this gate firing on this
# repo: a SECTION REFERENCE is not a count. "the §5 pointer rules" read as (5, rules)
# and "#3 files" as (3, files) -- and neither is groundable, because the author never
# claimed a quantity. `§` is not a `\w` character, so the original guard let it through.
_COUNT_RE = re.compile(
    r"\*{0,2}(?<![\w.§#])(\d[\d,]*)\*{0,2}\s+(?:\w+\s+)?(" + "|".join(_COUNT_NOUNS) + r")\b",
    re.IGNORECASE,
)

# Something that could re-derive a count. Presence of any of these near a claim is
# taken as grounding -- the checker verifies that a command was OFFERED, never that
# it still returns the stated number (that needs a shell, which this cannot use).
_DERIVATION_TOKENS = ("rg ", "grep ", "fd ", "find ", "git ", "wc -l", "ls ", "dotnet ")

# How many lines either side of a claim count as "adjacent".
GROUNDING_WINDOW = 3


# A hand-built mock that is not a claim about this repo. `illustrative` already
# exempts a FENCE via its info string (references/stamping.md), but a markdown table
# cannot carry one -- so the same contract is spelled as an HTML comment on the line
# above. Without it, a skill template's mock report table (rows of `` `file.php:42` ``)
# was four UNRESOLVED_CITATION errors: the gate failing a file that is correct, which
# is the failure mode that teaches people to ignore the gate.
_ILLUSTRATIVE_MARKER_RE = re.compile(r"^[ \t]*<!--[ \t]*illustrative[ \t]*-->[ \t]*$")


def illustrative_line_numbers(text):
    """1-based line numbers an `<!-- illustrative -->` marker covers: the marker line
    and every following line up to the first blank one. Blank-delimited so the marker
    scopes to the single block beneath it and cannot silence a whole file.

    A marker QUOTED inside a fence scopes to nothing. `references/stamping.md` teaches
    the marker by showing it in a ```markdown fence, and since a closing fence line is
    not blank, the scope used to walk out of the fence and silence the prose beneath --
    so the one file documenting the feature disabled the check on whatever followed it.
    """
    out = set()
    lines = text.splitlines()
    fenced = _fenced_line_numbers(text)
    for i, line in enumerate(lines, 1):
        if i in fenced or not _ILLUSTRATIVE_MARKER_RE.match(line):
            continue
        out.add(i)
        for j in range(i + 1, len(lines) + 1):
            if not lines[j - 1].strip() or j in fenced:
                break
            out.add(j)
    return out


def iter_citations(text):
    """Yield (lineno, path, line_number) for each backticked `path:line` citation
    in PROSE. Fenced blocks and `<!-- illustrative -->` blocks are skipped: a path
    inside a code sample or a mock table is illustration, and treating it as a
    citation is the fastest way to make this check noisy."""
    skip = _fenced_line_numbers(text) | illustrative_line_numbers(text)
    for i, line in enumerate(text.splitlines(), 1):
        if i in skip:
            continue
        for m in _CITATION_RE.finditer(line):
            yield i, m.group(1), int(m.group(2))


def iter_count_claims(text):
    """Yield (lineno, number, noun, grounded) for each numeric claim about the
    codebase. `grounded` is True when a plausible re-derivation command appears
    within GROUNDING_WINDOW lines -- including inside a fence, since that is
    exactly where a command belongs."""
    lines = text.splitlines()
    skip = _fenced_line_numbers(text) | illustrative_line_numbers(text)
    for i, line in enumerate(lines, 1):
        if i in skip:
            continue
        for m in _COUNT_RE.finditer(line):
            lo = max(0, i - 1 - GROUNDING_WINDOW)
            hi = min(len(lines), i + GROUNDING_WINDOW)
            window = "\n".join(lines[lo:hi])
            grounded = any(tok in window for tok in _DERIVATION_TOKENS)
            yield i, m.group(1).replace(",", ""), m.group(2).lower(), grounded


# `npm run <script>` / `yarn <script>` / `pnpm run <script>` cited in prose. Only
# the npm-family form is matched: it is the one whose script list is declarative
# and cheap to read (package.json "scripts"), so a miss is provable rather than
# guessed.
#
# `composer run` / `composer run-script` is matched under its own runner name so a
# PHP repo's composer.json scripts are never checked against an npm script list (and
# vice versa in a mixed monorepo). Bare `composer <name>` is deliberately NOT matched:
# `install`, `update`, `require` and ~30 more are built-in Composer commands, and
# UNDEFINED_SCRIPT is an error-level finding, so guessing would fail the gate on
# correct prose.
_SCRIPT_RE = re.compile(
    r"\b(?:npm|pnpm)\s+run\s+(?P<npm>[A-Za-z0-9:_-]+)"
    r"|\bcomposer\s+run(?:-script)?\s+(?P<composer>[A-Za-z0-9:_-]+)"
)

# Naming a script that does not exist is sometimes the POINT: a doc recording that
# `npm run e2e` was never defined, or a template showing a generic ecosystem default
# that a repo-specific block overrides. Both are correct prose containing an
# undefined name, and flagging them makes the check loudest on the files that
# document the problem.
#
# Same shape as _DERIVATION_TOKENS: a marker within GROUNDING_WINDOW lines reads as
# narration rather than instruction. Deliberately errs toward silence -- a missed
# undefined script costs one failed command, a false error costs trust in the gate.
_NARRATION_TOKENS = (
    "never",
    "not defined",
    "does not exist",
    "doesn't exist",
    "no longer",
    "drift",
    "corrected",
    "typically",
    "for example",
    "e.g.",
    "ecosystem default",
    "instead of",
    "was removed",
    "renamed",
    "only ever",
    "were cited",
    "exists to catch",
)


def _script_families(known_scripts):
    """Normalize `known_scripts` to {runner: set(names)} or None.

    A bare set/iterable is the npm family, which is what every caller meant before
    composer support existed -- so a pre-existing call site keeps its behavior
    without being rewritten.
    """
    if known_scripts is None:
        return None
    if isinstance(known_scripts, dict):
        return {runner: set(names or ()) for runner, names in known_scripts.items()}
    return {"npm": set(known_scripts)}


def split_frontmatter(text):
    """(frontmatter_text, body_start_lineno) for a file opening with `---`, else
    (None, 1). Frontmatter is only frontmatter at the very top of the file."""
    if not text.startswith("---\n"):
        return None, 1
    rest = text[4:]
    end = rest.find("\n---")
    if end == -1:
        return None, 1
    return rest[:end], text[: 4 + end].count("\n") + 2


def iter_frontmatter_problems(text):
    """Yield (lineno, detail) for frontmatter that will not parse as YAML.

    Deliberately NOT a YAML parser -- this module is stdlib-only, and a hand-rolled
    parser would trade one class of false report for a worse one. It detects the
    single failure that actually occurs in hand-written instruction files: an
    unquoted scalar containing a colon-space, which YAML reads as a nested mapping
    and rejects.

        description: Observer components: side-effect containers   <- invalid
        description: "Observer components: side-effect containers"  <- fine

    That one shape accounted for 17 of 21 rules in a real migration, any of which
    may silently fail to load. Tabs are flagged too: YAML forbids them as
    indentation, and an editor that inserts one leaves no visible trace.
    """
    fm, _ = split_frontmatter(text)
    if fm is None:
        if text.startswith("---\n"):
            yield 1, "frontmatter opened with --- but never closed"
        return
    for offset, line in enumerate(fm.split("\n"), 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line:
            yield offset, "tab in frontmatter -- YAML forbids tabs as indentation"
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+):\s+(.*)$", line)
        if not m:
            continue
        value = m.group(2).strip()
        if not value or value[0] in "\"'|>[{#&*!":
            continue
        if ": " in value or value.endswith(":"):
            yield (
                offset,
                "%s: unquoted value contains ': ' -- quote it or YAML reads a nested mapping"
                % m.group(1),
            )


def iter_path_globs(text):
    """Yield (lineno, glob) for each entry under a frontmatter `paths:` key.

    Reads only the block sequence directly under `paths:`, which is the form every
    template and every real rule uses. A flow sequence (`paths: [a, b]`) is handled
    too, since YAML accepts it and someone will eventually write it.
    """
    fm, _ = split_frontmatter(text)
    if fm is None:
        return
    lines = fm.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^paths:\s*(.*)$", line)
        if not m:
            continue
        inline = m.group(1).strip()
        if inline.startswith("["):
            for item in inline.strip("[]").split(","):
                item = item.strip().strip("\"'")
                if item:
                    yield i + 2, item
            return
        for j in range(i + 1, len(lines)):
            entry = re.match(r"^\s+-\s+(.*)$", lines[j])
            if not entry:
                if lines[j].strip() and not lines[j].startswith(" "):
                    break
                continue
            yield j + 2, entry.group(1).strip().strip("\"'")
        return


def iter_script_citations(text):
    """Yield (lineno, runner, script_name) for each `npm run <x>` / `composer run <x>`
    presented as a command to run, where runner is "npm" or "composer". Narration
    about a script -- that it never existed, was renamed, or is a generic default --
    is skipped; see _NARRATION_TOKENS.

    Unlike citations, fenced lines COUNT: a command block is exactly where a script
    name gets copied from, so an undefined name inside a fence is the more dangerous
    of the two.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        matches = list(_SCRIPT_RE.finditer(line))
        if not matches:
            continue
        lo = max(0, i - 1 - GROUNDING_WINDOW)
        hi = min(len(lines), i + GROUNDING_WINDOW)
        # Collapse whitespace before matching: markdown prose wraps at 80 columns,
        # so a two-word marker ("only ever", "was renamed") is routinely split by a
        # newline and a line-wise search would miss it.
        window = " ".join(" ".join(lines[lo:hi]).lower().split())
        if any(tok in window for tok in _NARRATION_TOKENS):
            continue
        for m in matches:
            for runner in ("npm", "composer"):
                if m.group(runner) is not None:
                    yield i, runner, m.group(runner)


def check_instructions(text, resolve, kind=None, glob_matches=None, known_scripts=None):
    """Findings for one instruction file, in check-docs' (sev, code, lineno,
    detail) shape minus the path, which the caller owns.

    `resolve(path, line_number)` returns True when that path exists in the repo AND
    has at least that many lines. Injected rather than hard-coded so the extraction
    logic stays a pure function.

    `kind` is "rule", "skill", or None. It gates MISSING_PATHS only: a skill without
    `paths:` is normal (it loads on invocation), a rule without it taxes every
    session. Pass None to skip that check when the kind is unknown.

    `glob_matches(glob)` returns the number of repo files a `paths:` entry matches;
    `known_scripts` is the set of defined script names. Both optional -- omit either
    and its check is skipped rather than reported as a failure, so the function stays
    usable with no repo on hand.

    Severity rests on one question: does the finding mean the file is not doing what
    it claims?

    - UNRESOLVED_CITATION -- the file said "look here" and there is nothing there.
    - INVALID_FRONTMATTER -- the file may not load AT ALL. The most expensive
      failure in the set, and the quietest: a rule that fails to parse is simply
      absent, with no error surfaced anywhere.
    - MISSING_PATHS -- an unscoped rule loads on every session including ones that
      never touch a matching file.
    - DEAD_GLOB -- the rule parses, loads, and can never fire.
    - UNDEFINED_SCRIPT -- the command does not exist; anyone copying it gets an
      error.

    UNGROUNDED_COUNT stays a warning -- a number without a nearby command is a
    maintenance smell, not proof of a wrong number, and treating it as fatal would
    make the gate unusable on prose-heavy files.
    """
    findings = []
    for lineno, detail in iter_frontmatter_problems(text):
        findings.append(("error", "INVALID_FRONTMATTER", lineno, detail))
    globs = list(iter_path_globs(text))
    if kind == "rule" and not globs:
        # Warning, not error, on the same reasoning as UNGROUNDED_COUNT: some rules
        # are always-on by design. A rule about WHEN to reach for a tool ("fetch docs
        # before answering about a library") has no file shape to scope to, and
        # claude-configs' own config/rules/context7.md is exactly that. Erroring here
        # would fail a correct file and push people to invent a bogus glob.
        # The cost is real and worth surfacing -- an unscoped rule is paid every
        # session -- but it is a deliberate trade, not a defect.
        findings.append(
            (
                "warn",
                "MISSING_PATHS",
                1,
                "rule has no paths: -- it loads on every session; intended?",
            )
        )
    if glob_matches is not None:
        for lineno, glob in globs:
            # An angle-bracketed glob is an unfilled placeholder, not a dead rule.
            # The scaffolded EXAMPLE ships one deliberately so it matches nothing and
            # costs no context until someone fills it in -- flagging that would make a
            # correct scaffold fail its own gate.
            if "<" in glob and ">" in glob:
                continue
            if glob_matches(glob) == 0:
                findings.append(
                    (
                        "error",
                        "DEAD_GLOB",
                        lineno,
                        "%s matches no file -- the rule can never fire" % glob,
                    )
                )
    families = _script_families(known_scripts)
    if families is not None:
        for lineno, runner, script in iter_script_citations(text):
            # A runner absent from the mapping is unmanifested, not undefined: a
            # PHP-only repo has no package.json to check `npm run x` against, and
            # reporting it would fail the gate on a command we cannot verify.
            if runner in families and script not in families[runner]:
                findings.append(
                    (
                        "error",
                        "UNDEFINED_SCRIPT",
                        lineno,
                        "%s run %s is not a defined script" % (runner, script),
                    )
                )
    for lineno, path, line_number in iter_citations(text):
        if not resolve(path, line_number):
            findings.append(("error", "UNRESOLVED_CITATION", lineno, "%s:%d" % (path, line_number)))
    for lineno, number, noun, grounded in iter_count_claims(text):
        if not grounded:
            findings.append(
                (
                    "warn",
                    "UNGROUNDED_COUNT",
                    lineno,
                    "%s %s -- no re-derivation command within %d lines"
                    % (number, noun, GROUNDING_WINDOW),
                )
            )
    return findings


# --- check-docs: the documentation grounding gate -------------------------------

# Directories a docs walk never descends into (dependency trees, VCS internals,
# agent/plugin working directories, and this skill's own pre-stamp scaffold).
#
# An AGENT WORKING DIRECTORY holds a plugin's own scratch artifacts -- superpowers'
# `plans/` and `specs/`, this skill's pre-stamp scaffold. They are working notes, not
# the repo's documentation: they are not in any docs tier, they are written by a tool
# rather than authored for a reader, and they deliberately quote pre-sanitization
# sources. Grounding them reports dozens of findings no one will ever act on, which is
# the noise that gets a gate switched off. `test/check_clean.sh` carves out the same
# two names for the same reason.
_EXCLUDE_DIRS = {
    "node_modules",
    "vendor",
    "dist",
    "build",
    ".venv",
    "venv",
    ".tox",
    "site-packages",
    "target",
    ".git",
    ".onboard-repo-retired",
    ".superpowers",
    "superpowers",
}

# Directories the citation/glob index never walks. A SUPERSET of _EXCLUDE_DIRS, not a
# second opinion: when the two lists disagreed, `vendor/` was excluded from the docs
# walk but indexed for citations, so a vendored tree contributed both phantom
# UNGROUNDED_COUNT context and phantom resolutions for shorthand citations.
_SKIP_DIRS = _EXCLUDE_DIRS | {
    "bin",
    "obj",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}


def _relparts(root, path):
    """`path`'s parts RELATIVE to `root`, or None when it does not sit under it.

    Every exclusion test goes through this. Relative on purpose: testing the
    ABSOLUTE parts excludes an entire repo that merely happens to be checked out
    under a directory called `build`, `vendor` or `dist` -- every file in it
    vanishes from the index at once, which reports a correct repo as one whose
    globs match nothing and whose citations name no file.
    """
    try:
        return path.relative_to(root).parts
    except ValueError:
        return None


def _is_skipped(root, path):
    """True when `path` sits under a citation/glob-index skip dir RELATIVE to `root`.

    A path outside `root` entirely is skipped: the index is a picture of ONE repo,
    and something the base cannot even address is not part of it.
    """
    rel = _relparts(root, path)
    if rel is None:
        return True
    return bool(_SKIP_DIRS.intersection(rel))


def _is_excluded(relparts):
    if any(p in _EXCLUDE_DIRS for p in relparts):
        return True
    # the skill's own templates/** (pre-stamp layout): .../skills/<x>/templates/...
    for i, p in enumerate(relparts):
        if p == "skills" and "templates" in relparts[i + 1 :]:
            return True
    return False


# Directory names that identify a docs TIER. A root the operator names may already sit
# inside one (`check-docs docs/manual`) or BE one, so the tier parts of the root's own
# path have to be carried into each file's relparts -- otherwise naming the tier directly
# loses the tier, which is the silent-off failure the relative test exists to prevent.
_TIER_DIRS = {"manual", "internals", "adr", "archive"}


def _tier_prefix(root):
    """The trailing tier components of `root` itself, e.g. docs/manual -> ('manual',).

    Scanned from the END and only while every component is a tier name, so a repo
    checked out under a directory called `archive` contributes nothing: in
    `/x/archive/myrepo/docs` the last component (`docs`) is not a tier name, so the
    scan stops immediately and the live pages below stay live. `docs/archive` yields
    ('archive',) because the tier name IS the tail.
    """
    parts = pathlib.Path(root).parts
    cut = len(parts)
    while cut > 0 and parts[cut - 1] in _TIER_DIRS:
        cut -= 1
    return parts[cut:]


def _iter_markdown_files(roots):
    """Yield (path, relparts) for each .md under the roots (files or walked dirs),
    honoring _EXCLUDE_DIRS. Raises FileNotFoundError only via the caller's checks.

    `relparts` is the path's parts relative to the root it was found under, PREFIXED
    with any tier components of that root -- the only sound basis for a TIER test.
    Keying a tier off the absolute parts made every check that asks "which tier is this
    page in?" answer from the checkout location: a repo living under a directory named
    `archive` had grounding silently disabled on its live pages, and one under `adr` had
    every page reported as a malformed decision record. Dropping the root's own tier
    components instead lost the tier whenever the operator named it directly
    (`check-docs docs/archive`, or a single file path).
    """
    seen = []
    seen_resolved = set()

    def _add(path, relparts):
        rp = path.resolve()
        if rp not in seen_resolved:
            seen_resolved.add(rp)
            seen.append((path, relparts))

    for root in roots:
        p = pathlib.Path(root)
        if p.is_file():
            # dedup: a root repeated (e.g. AGENTS.md listed twice) is scanned once.
            # The tier comes from the named path itself: `check-docs docs/archive/old.md`
            # is still an archive page, so its own directories carry the tier.
            _add(p, _tier_prefix(p.parent) + (p.name,))
            continue
        if not p.is_dir():
            continue
        prefix = _tier_prefix(p)
        for f in sorted(p.rglob("*.md")):
            rel = f.relative_to(p).parts
            if not _is_excluded(rel[:-1]):
                _add(f, prefix + rel)
    return seen


def _within_roots(target_path, root_paths):
    try:
        tp = target_path.resolve()
    except OSError:
        return False  # an un-resolvable target (e.g. ENAMETOOLONG) is not in-roots
    for r in root_paths:
        try:
            rp = pathlib.Path(r).resolve()
            tp.relative_to(rp)
            return True  # inside a dir root, or equal to a file root
        except (ValueError, OSError):
            continue
    return False


def _check_links(f, text, roots):
    findings = []
    for _disp, target, lineno in iter_markdown_links(text):
        if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", target) or target.startswith("/"):
            continue  # scheme/absolute
        path, _sep, frag = target.partition("#")
        if path == "":  # same-file anchor
            if frag and frag.lower() not in {s.lower() for s in heading_slugs(text)}:
                findings.append(("error", "BROKEN_ANCHOR", str(f), lineno, "#" + frag))
            continue
        tgt = f.parent / path
        try:
            relparts = tgt.resolve().parts
            exists = tgt.exists()
        except OSError:
            # un-stattable target (e.g. a path component over NAME_MAX): a docs-content
            # problem, not a gate-usage error — record a warn and keep going; never let
            # one pathological link abort the whole run to exit 2 (review S3; cf. S2-H2).
            findings.append(("warn", "BROKEN_LINK", str(f), lineno, target))
            continue
        in_roots = _within_roots(tgt, roots)
        excluded = _is_excluded(relparts)
        if not exists:
            sev = "error" if (in_roots and not excluded) else "warn"
            findings.append((sev, "BROKEN_LINK", str(f), lineno, target))
            continue
        if frag and tgt.suffix == ".md" and in_roots and not excluded:
            if re.match(r"^L\d+", frag):
                continue  # line anchor on a code file elsewhere
            try:
                other = tgt.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if frag.lower() not in {s.lower() for s in heading_slugs(other)}:
                findings.append(("error", "BROKEN_ANCHOR", str(f), lineno, target))
    return findings


def _check_tables(f, text):
    findings = []
    for lineno, kind, got, want in table_cell_errors(text):
        if kind == "error":
            findings.append(
                (
                    "error",
                    "MALFORMED_TABLE",
                    str(f),
                    lineno,
                    "row has %d cells, header has %d" % (got, want),
                )
            )
        else:
            findings.append(
                (
                    "warn",
                    "TABLE_SHORT_ROW",
                    str(f),
                    lineno,
                    "row has %d cells, header has %d" % (got, want),
                )
            )
    return findings


_PLACEHOLDER_RE = re.compile(r"\{\{TODO:[^}]*\}\}")


def _load_coverage(coverage_file):
    """Parse the committed coverage record ([{surface, slug, tier, page,
    status}, ...]); None when no --coverage was given. Malformed JSON, wrong
    shape (not a list of objects), or an unreadable file surface as
    ValueError/OSError to the caller, which turns those into a clean exit 2
    with an accurate 'malformed coverage record' message."""
    if coverage_file is None:
        return None
    data = json.loads(pathlib.Path(coverage_file).read_text(encoding="utf-8"))
    if not (isinstance(data, list) and all(isinstance(rec, dict) for rec in data)):
        raise ValueError("coverage record must be a list of objects")
    return data


def _check_placeholders(f, text, has_coverage):
    if f.name.endswith("-TEMPLATE.md"):
        return []
    findings = []
    for i, line in enumerate(text.split("\n"), start=1):
        if _PLACEHOLDER_RE.search(line):
            sev = "error" if has_coverage else "warn"
            findings.append((sev, "PLACEHOLDER", str(f), i, line.strip()))
    return findings


# Languages whose fences are source, not command output. A fence tagged with one of
# these is exempt from the grounding check entirely -- a C# snippet or a mermaid diagram
# is authored illustration, and demanding `capture=` or `illustrative` on it would force
# the author to write a falsehood.
_CODE_LANGS = {
    "python",
    "py",
    "json",
    "jsonc",
    "json5",
    "diff",
    "patch",
    "yaml",
    "yml",
    "toml",
    "js",
    "jsx",
    "javascript",
    "ts",
    "tsx",
    "typescript",
    "go",
    "rust",
    "rs",
    "html",
    "xhtml",
    "css",
    "scss",
    "sass",
    "less",
    "c",
    "h",
    "cpp",
    "cc",
    "hpp",
    "objc",
    "objectivec",
    "java",
    "kotlin",
    "kt",
    "kts",
    "swift",
    "scala",
    "groovy",
    "dart",
    "ruby",
    "rb",
    "php",
    "perl",
    "lua",
    "r",
    "julia",
    "elixir",
    "erlang",
    "haskell",
    "clojure",
    "fsharp",
    "fs",
    "csharp",
    "cs",
    "cshtml",
    "razor",
    "vb",
    "sql",
    "graphql",
    "proto",
    "xml",
    "xaml",
    "svg",
    "ini",
    "cfg",
    "conf",
    "properties",
    "env",
    "dockerfile",
    "makefile",
    "cmake",
    "nix",
    "hcl",
    "terraform",
    "mermaid",
    "plantuml",
    "dot",
    "tex",
    "latex",
}

# Shell-ish fences are deliberately NOT in _CODE_LANGS: a transcript pasted under ```shell
# is exactly the thing grounding exists to police. They get the prompt test in
# _is_output_shaped instead, so a pure command list stays exempt while a command plus its
# output still needs capture=<slug> or illustrative.
_SHELL_LANGS = {
    "sh",
    "shell",
    "bash",
    "zsh",
    "fish",
    "console",
    "shell-session",
    "shellsession",
    "powershell",
    "ps1",
    "pwsh",
    "bat",
    "cmd",
}
_READONLY_CMD = re.compile(
    r"^\s*[$#]\s*(ls|cat|git status|git log|tree|pwd|echo|"
    r"\./install\.\w+ --plan|.*--plan\b|.*--help\b|.*-h\b)"
)
_CMD_LINE = re.compile(r"^\s*[$#]\s+\S")


def _first_token_lang(info):
    return (info.split() or [""])[0].lower()


def _tags_of(info):
    toks = info.split()
    tags = {}
    illustrative = "illustrative" in toks
    for t in toks:
        if t.startswith("capture="):
            tags["capture"] = t[len("capture=") :]
    return tags, illustrative


def _is_output_shaped(body, shell_fenced=False):
    lines = [ln for ln in body.split("\n") if ln.strip()]
    if not lines:
        return False
    if shell_fenced:
        # `#` opens a comment in every shell, but _CMD_LINE reads it as a root prompt, so
        # an annotated command list would otherwise look like output. Drop comments first.
        lines = [ln for ln in lines if not ln.lstrip().startswith("#")]
        if not lines:
            return False
        # A shell fence counts as a transcript only when it shows a prompt AND a line that
        # is not one -- i.e. a command together with what it printed. With no prompt at
        # all the block is a bare command list (`dotnet build ...`), which docs write
        # constantly; treating that as output would flag nearly every install section.
        # Known gap: output pasted with no command and no prompt is exempt too. That is
        # accepted -- the two are indistinguishable without a regex that guesses whether a
        # line "looks like" a command, which cannot be done without also matching prose.
        prompts = [ln for ln in lines if _CMD_LINE.match(ln)]
        return bool(prompts) and len(prompts) < len(lines)
    return not all(_CMD_LINE.match(ln) for ln in lines)


def _is_frozen_tier(relparts):
    """True for a page in the `archive/` docs tier, tested ROOT-RELATIVE.

    The IA declares `docs/archive/**` frozen -- never edited (references/rubric.md,
    templates/docs-ia/AGENTS.md). Demanding a provenance tag there asked for an edit
    the same skill forbids, so an adopted historical record could never pass the gate.
    Only the GROUNDING checks are skipped: a link in an archived page still gets
    rebased mechanically when a target moves, so BROKEN_LINK there is still actionable.
    """
    return "archive" in relparts[:-1]


def _check_grounding(f, text, captures_dir):
    findings = []
    for info, body, lineno in iter_fenced_blocks(text):
        tags, illustrative = _tags_of(info)
        # An explicit capture= tag is verified whatever the fence's language or shape. The
        # convention puts the command in a bash fence and the output ALONE in a `console
        # capture=<slug>` fence; console is a shell language, and a prompt-less shell fence
        # reads as a bare command list below -- so the tag was never read and a tampered
        # capture passed the gate (found in brainiac-pipeline, 2026-10-12).
        if "capture" not in tags:
            lang = _first_token_lang(info)
            if lang in _CODE_LANGS:
                continue
            if not _is_output_shaped(body, shell_fenced=lang in _SHELL_LANGS):
                continue
        if "capture" in tags:
            slug = tags["capture"]
            if captures_dir is None:
                # Distinct from UNGROUNDED_OUTPUT on purpose. Folding the two together
                # reported a correctly-captured block as ungrounded whenever --captures
                # was simply left off, which sends the operator to edit a correct doc
                # instead of fixing the invocation. Still error-level: an unverified
                # capture must not pass silently.
                findings.append(
                    (
                        "error",
                        "CAPTURES_NOT_CHECKED",
                        str(f),
                        lineno,
                        "capture=%s not verified -- fix the INVOCATION, not the doc: "
                        "re-run with --captures DIR" % slug,
                    )
                )
                continue
            cap_path = pathlib.Path(captures_dir) / (slug + ".txt")
            try:
                cap = cap_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                cap = None
            if cap is None or not output_subsequence_ok(body, cap):
                findings.append(("error", "UNGROUNDED_OUTPUT", str(f), lineno, "capture=" + slug))
            continue
        if illustrative:
            has_cmd = any(_CMD_LINE.match(ln) for ln in body.split("\n"))
            has_output = any(ln.strip() and not _CMD_LINE.match(ln) for ln in body.split("\n"))
            if has_cmd and has_output and any(_READONLY_CMD.match(ln) for ln in body.split("\n")):
                findings.append(
                    (
                        "warn",
                        "CAPTURABLE_ILLUSTRATIVE",
                        str(f),
                        lineno,
                        "illustrative output could be captured",
                    )
                )
            continue
        findings.append(
            (
                "error",
                "UNTAGGED_OUTPUT",
                str(f),
                lineno,
                "output block needs capture=<slug> or illustrative",
            )
        )
    return findings


def _real_manual_dirs(base):
    """Non-excluded `manual/` dirs under base (plus base itself when it IS a
    manual/ dir), honoring _EXCLUDE_DIRS/templates — mirrors _iter_markdown_files
    so a manual/ under node_modules/ or vendor/ is not treated as real (review M3)."""
    dirs = []
    if base.is_dir():
        for man in base.rglob("manual"):
            if man.is_dir() and not _is_excluded(man.relative_to(base).parts):
                dirs.append(man)
        if base.name == "manual":
            dirs.append(base)
    return dirs


def _manual_real_pages(roots):
    """.md files under any docs/manual/ in scope, excluding README/index (which
    are navigation, not content) and any dependency-tree path (_is_excluded)."""
    pages = []
    for r in roots:
        p = pathlib.Path(r)
        base = p if p.is_dir() else p.parent
        for man in _real_manual_dirs(base):
            for f in man.rglob("*.md"):
                if f.stem.lower() in ("readme", "index"):
                    continue
                if _is_excluded(f.relative_to(base).parts):
                    continue
                pages.append(f)
    return pages


def _resolve_coverage_page(page, roots):
    """Coverage `page` values are repo-root-relative (e.g. 'docs/manual/x.md').
    Try the path as-is (cwd-relative), then anchored under each ancestor of
    each root, so a coverage record travels with the checked tree regardless
    of the caller's cwd. A candidate is only accepted when it lands WITHIN the
    checked roots (review I1): otherwise the ancestor walk could bind a stray
    same-named file above the root and mask a genuinely-missing page. Returns
    None when no in-roots candidate exists (a non-str page, or nothing within
    the roots): the caller MUST treat None as a missing page. A bare
    `return direct` here would re-leak the rejected out-of-root path and defeat
    the guard (review S1-C1). Every `.is_file()` probe is OSError-guarded so a page
    value that cannot even be stat'd (e.g. a 20000-char string -> ENAMETOOLONG) is a
    non-candidate (-> None -> EMPTY_TIER), never a crash that aborts the whole gate
    (review S2-H2)."""
    if not isinstance(page, str):
        return None

    def _is_file(p):
        try:
            return p.is_file()
        except OSError:
            return False

    direct = pathlib.Path(page)
    if _is_file(direct) and _within_roots(direct, roots):
        return direct
    for r in roots:
        rp = pathlib.Path(r)
        for anchor in [rp] + list(rp.parents):
            cand = anchor / page
            if _is_file(cand) and _within_roots(cand, roots):
                return cand
    return None


def _check_empty_tier(roots, coverage):
    """Coverage-driven: error when a principal surface's page is null/missing/
    empty (authoring is expected); warn when there is no coverage record at
    all and the manual tier has zero authored (non-README/index) pages."""
    findings = []
    if coverage is not None:
        # A principal page counts as covered only when it is a GENUINE authored
        # manual page (review S2-H1): reuse _manual_real_pages so the coverage gate
        # is self-consistent with EMPTY_TIER's no-coverage branch. This rejects a
        # page pointing at the coverage JSON, a README/nav index, an excluded-dir
        # file, or any in-roots-but-not-a-manual-page target that used to mask.
        real_pages = _manual_real_pages(roots)
        for rec in coverage:
            if rec.get("tier") != "principal":
                continue
            page = rec.get("page")
            ok = False
            if isinstance(page, str) and page:
                resolved = _resolve_coverage_page(page, roots)
                if resolved is not None:  # None => no in-roots candidate => missing
                    try:
                        # Compare by file IDENTITY (samefile), not resolved-path string
                        # equality: resolve() preserves case on macOS/Windows
                        # case-insensitive filesystems, so a case-variant page
                        # (Usage.md vs on-disk usage.md) would spuriously fail a
                        # string-set membership and emit a false EMPTY_TIER (review S3).
                        # samefile also handles symlinks correctly.
                        ok = (
                            any(resolved.samefile(p) for p in real_pages)
                            and resolved.read_text(encoding="utf-8", errors="replace").strip() != ""
                        )
                    except OSError:
                        ok = False
            if not ok:
                findings.append(
                    (
                        "error",
                        "EMPTY_TIER",
                        page if isinstance(page, str) and page else "docs/.onboard-coverage.json",
                        1,
                        "principal surface %r has no page" % rec.get("slug"),
                    )
                )
        return findings
    # No coverage record: warn if a manual tier is in scope but has zero
    # authored pages.
    if _manual_real_pages(roots):
        return findings
    has_manual = any(_real_manual_dirs(pathlib.Path(r)) for r in roots)
    if has_manual:
        findings.append(
            ("warn", "EMPTY_TIER", "docs/manual", 1, "manual tier has no authored pages")
        )
    return findings


def _check_forbidden(f, text, forbidden):
    """Opt-in via --forbidden a,b; error for each token found in the raw file
    text. Scans raw text (not just fenced blocks) since secrets sit in code
    fences. Empty default = no-op."""
    findings = []
    for tok in forbidden:
        if tok and tok in text:
            for i, line in enumerate(text.split("\n"), start=1):
                if tok in line:
                    findings.append(("error", "FORBIDDEN_TOKEN", str(f), i, tok))
                    break
    return findings


def _check_unresolved_command(f, text, captures_dir):
    """Honest default (spec 4.2): skipped unless a committed authoritative
    usage snapshot exists under captures_dir (e.g. <slug>-help.txt). A README
    "usage" block is non-authoritative and never a completeness oracle, so
    this always returns [] for now; the authoritative-surface path is a
    documented future extension once such a snapshot format is adopted."""
    return []


# A generous per-file size cap. Real docs are KB-scale; a file above this is
# pathological/generated input, so it is recorded ONCE as FILE_TOO_LARGE and its
# per-file content scanners are skipped (bounds the worst-case scan cost).
_MAX_DOC_BYTES = 1_000_000


# An absolute home directory, in any of the three shapes a developer machine produces.
# `redact` normalizes these out of a CAPTURE, but an ADOPTED page never passes through
# it -- §3.6 moves a repo's existing docs verbatim -- so a page carrying the operator's
# home path lands in permanent history with nothing objecting.
# No trailing separator is required: the three prefixes are already unambiguous, and
# demanding one missed the Windows shape entirely, whose separator is `\` not `/`.
# The user segment must contain a WORD character and is matched without `.`: `/Users/...`
# is the placeholder every doc uses to NAME this forbidden shape, and flagging it made
# the page that documents the rule the one page that cannot satisfy it.
_HOME_PATH_RE = re.compile(
    r"/home/(?=[\w-]*\w)[\w-]+"  # Linux
    r"|/Users/(?=[\w-]*\w)[\w-]+"  # macOS
    r"|[A-Za-z]:\\Users\\(?=[\w-]*\w)[\w-]+"  # Windows
)

# Placeholder user segments that are the DOCUMENTATION of a home path, not one: a page
# teaching `~/.claude/` or a redaction rule has to be able to write the shape down.
# Deliberately short -- only the conventional stand-ins. A plausible-looking name like
# `someone` is NOT here: it is indistinguishable from a real login, and the cost of
# guessing wrong is a leak that ships.
_HOME_PATH_PLACEHOLDERS = {"user", "username", "you", "youruser"}


def _illustrative_fence_lines(text):
    """1-based line numbers inside a fence tagged `illustrative`.

    The tag's two spellings must exempt the same thing: `illustrative_line_numbers`
    covers the HTML-comment form (for tables), this covers the info-string form.
    """
    out = set()
    for info, body, lineno in iter_fenced_blocks(text):
        if "illustrative" not in info.split():
            continue
        # lineno is the fence's opening line; the body starts on the next one.
        for k in range(body.count("\n") + 2):
            out.add(lineno + k)
    return out


def _check_leaked_paths(f, text):
    """LEAKED_PATH -- an absolute home directory in a committed doc.

    A warning rather than an error on purpose: the usual source is an adopted legacy
    page, which the operator may not be free to rewrite in the same change (and
    `docs/archive/**` is frozen outright). Failing the gate would repeat the mistake
    `_is_frozen_tier` exists to undo -- demanding an edit the IA forbids.

    `illustrative` blocks are exempt, for the same reason they are exempt from every
    other grounding check: a doc that explains what `redact` strips must be able to
    show a home path without being reported for the example it is making.
    """
    findings = []
    skip = illustrative_line_numbers(text) | _illustrative_fence_lines(text)
    for i, line in enumerate(text.splitlines(), 1):
        if i in skip:
            continue
        m = _HOME_PATH_RE.search(line)
        if m and m.group(0).rsplit("\\", 1)[-1].rsplit("/", 1)[-1].lower() not in (
            _HOME_PATH_PLACEHOLDERS
        ):
            findings.append(
                (
                    "warn",
                    "LEAKED_PATH",
                    str(f),
                    i,
                    "absolute home path %s -- rewrite as a repo-relative path or ~" % m.group(0),
                )
            )
    return findings


def _check_showcase(f, text, relparts):
    """NO_SHOWCASE -- a manual page that shows commands but never what they produce.

    §3.7 authors manual pages showcase-first: lead with rendered output. The grounding
    checks can only catch output that is present and UNTAGGED; a page consisting purely
    of command fences has no output to tag, so it passes every existing check while
    doing exactly what the voice rule forbids. Observed on a real run: ten `bash`
    fences, one `illustrative` block, zero captures, `check-docs` clean.

    A warning, not an error -- whether a given page owes the reader an output block is a
    judgement, and the §3.7 reviewer pass is the intended enforcement. This exists so
    the omission is at least visible when that pass is skipped.

    The tier test is ROOT-RELATIVE: keyed off the absolute parts, a repo checked out
    under a directory named `manual` had every page in it reported.
    """
    if "manual" not in relparts[:-1] or relparts[-1] == "README.md":
        return []
    shell = grounded = 0
    for info, body, lineno in iter_fenced_blocks(text):
        lang = _first_token_lang(info)
        tags, illustrative = _tags_of(info)
        if "capture" in tags or illustrative:
            grounded += 1
        elif lang in _SHELL_LANGS:
            # A fence that is itself a transcript IS rendered output, tagged or not.
            # Counting it as a bare command block reported a page for showing nothing
            # while it showed a command AND what it printed; the untagged case is
            # already UNTAGGED_OUTPUT's business, not this check's.
            if _is_output_shaped(body, shell_fenced=True):
                grounded += 1
            else:
                shell += 1
    # A blockquoted fence is invisible to `_FENCE_RE` (anchored at ^[ \t]*), so a page
    # whose showcase is quoted -- the shape this repo's own output-styles.md uses --
    # counted zero grounded blocks and could not be cleared by tagging anything.
    if shell and not grounded and not _has_blockquoted_showcase(text):
        return [
            (
                "warn",
                "NO_SHOWCASE",
                str(f),
                1,
                "%d command block(s) and no captured or illustrative output -- "
                "the page tells instead of showing" % shell,
            )
        ]
    return []


# A fence opened inside a blockquote. `_FENCE_RE` is anchored at `^[ \t]*`, so a
# `> ```text` line is not a fence to any of the grounding machinery -- which means a
# page cannot be blamed for the output it shows this way either.
_BLOCKQUOTED_FENCE_RE = re.compile(r"^[ \t]*>[ \t>]*(?:```|~~~)")


def _has_blockquoted_showcase(text):
    """True when a blockquoted fence appears in PROSE -- a showcase this gate cannot see.

    Scoped two ways, because the naive whole-file search was an escape hatch wide enough
    to drive through: a single blockquoted fence ANYWHERE silenced the page, including one
    merely QUOTED inside a code sample (so a page teaching blockquote syntax switched off
    its own check). Fenced lines are excluded, and the quote must carry a non-empty line
    beyond the fence markers -- an empty quoted fence shows nothing.

    KNOWN false negative: a quoted block that is not a showcase at all (a `> ```yaml`
    config snippet) still silences the page. Distinguishing it from quoted OUTPUT needs
    the same guess `_is_output_shaped` refuses to make, and the error runs in the safe
    direction -- NO_SHOWCASE is a warning, so under-reporting costs a nudge, while
    over-reporting demands an edit that tagging cannot satisfy. §3.7's reviewer pass is
    the real enforcement.
    """
    fenced = _fenced_line_numbers(text)
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        if i in fenced or not _BLOCKQUOTED_FENCE_RE.match(line):
            continue
        for follow in lines[i : i + 40]:
            stripped = follow.lstrip()
            if not stripped.startswith(">"):
                break
            content = stripped.lstrip("> \t")
            if content and not content.startswith(("```", "~~~")):
                return True
    return False


# `ADR-NNNN-<slug>.md`, the name `references/stamping.md` and the scaffolded
# ADR-TEMPLATE.md both specify. The three sections the template mandates, matched as
# HEADINGS (any level) rather than by substring: `### Context` is the same section at a
# different depth, and a `## Decision` quoted inside a fence is not a section at all.
_ADR_NAME_RE = re.compile(r"^ADR-\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
_ADR_SECTIONS = ("Context", "Decision", "Consequences")
# A lifecycle pointer ("superseded by ADR-0007", "§4 amended by [ADR-0013](...)")
# is the one edit the frozen-once-accepted convention allows, so a pointer that
# resolves to nothing is a record lying about where its replacement lives.
_ADR_POINTER_RE = re.compile(
    r"(?:superseded|amended|replaced)\s+by\s+\[?ADR-(\d{4})", re.IGNORECASE
)


def _check_adr(f, text, relparts):
    """ADR_NAMING / ADR_SHAPE -- a decision record that is one only by filename --
    plus the two lifecycle checks, ADR_INDEX_DRIFT and ADR_DANGLING_SUPERSEDE.

    The lifecycle pair exists because an ADR's body is frozen once accepted: the
    only maintained parts are the tier index and the status pointers, so those are
    exactly where drift lands. ADR_INDEX_DRIFT is present-based -- a tier with no
    README.md keeps no index, and inventing the requirement would flag every
    minimal repo. The reverse direction (an index row whose file is gone) is
    already a BROKEN_LINK. Both are warn: each asks for a bookkeeping edit, not a
    content decision.

    Observed on a real run: a dated spec was reclassified into `docs/adr/`, given an
    `# ADR-0001:` heading and a Status/Date block, and otherwise left as the spec --
    no Context/Decision/Consequences, and the original's own `Status:` and `Data:`
    lines still underneath, so the file carried two statuses and two dates. The name
    also skipped the `ADR-` prefix its own template sits next to.

    The tier test is ROOT-RELATIVE, and the frozen tier is exempt: `docs/archive/adr/`
    holds superseded records the IA forbids editing, so reporting their shape would
    demand an edit that cannot be made.
    """
    name = relparts[-1]
    if "adr" not in relparts[:-1] or name in ("README.md", "ADR-TEMPLATE.md"):
        return []
    if _is_frozen_tier(relparts):
        return []
    findings = []
    if not _ADR_NAME_RE.match(name):
        findings.append(
            (
                "warn",
                "ADR_NAMING",
                str(f),
                1,
                "%s does not match ADR-NNNN-<slug>.md" % name,
            )
        )
    headings = {h.strip().lower() for h in heading_texts(text)}
    missing = [s for s in _ADR_SECTIONS if s.lower() not in headings]
    if missing:
        findings.append(
            (
                "warn",
                "ADR_SHAPE",
                str(f),
                1,
                "missing %s -- an ADR renamed but not restructured still reads as its source"
                % ", ".join("## " + s for s in missing),
            )
        )
    m = re.match(r"^(ADR-\d{4})", name)
    idx = f.parent / "README.md"
    if m and idx.is_file():
        try:
            itext = idx.read_text(encoding="utf-8", errors="replace")
        except OSError:
            itext = None
        if itext is not None and ("[%s]" % m.group(1)) not in itext:
            findings.append(
                (
                    "warn",
                    "ADR_INDEX_DRIFT",
                    str(f),
                    1,
                    "%s has no [%s] row in the tier index README.md" % (name, m.group(1)),
                )
            )
    for pm in _ADR_POINTER_RE.finditer(text):
        num = pm.group(1)
        if name.startswith("ADR-%s-" % num):
            continue  # a record quoting its own transition is not a dangling pointer
        try:
            resolved = any(f.parent.glob("ADR-%s-*.md" % num))
        except OSError:
            continue
        if not resolved:
            findings.append(
                (
                    "warn",
                    "ADR_DANGLING_SUPERSEDE",
                    str(f),
                    text[: pm.start()].count("\n") + 1,
                    "'%s' resolves to no ADR-%s-*.md in this tier"
                    % (" ".join(pm.group(0).split()), num),
                )
            )
    return findings


def _resolve_only(only):
    """Resolve --only paths to a set of resolved paths, or None when unscoped.
    Resolution (not string compare) so `docs/./p.md`, a relative and an absolute
    spelling of the same page all scope to it."""
    if not only:
        return None
    out = set()
    for o in only:
        try:
            out.add(pathlib.Path(o).resolve())
        except OSError:
            continue
    return out


def _check_docs(roots, captures_dir, coverage, forbidden, only=None, tier_check=True):
    """Return (findings, exit_code). findings = list of (severity, code, file,
    lineno, detail). `coverage` is the already-parsed coverage record (or None).
    Read-only; per-file OSError skipped. A file larger than _MAX_DOC_BYTES is
    recorded once as a FILE_TOO_LARGE warn and its per-file content checks are
    skipped (a defensive backstop, not a silent ignore).

    `only` restricts which files EMIT findings; the roots are still walked in full
    so link severity and tier exemptions keep resolving against the whole tree
    (see the module docstring). `tier_check=False` drops the tree-wide EMPTY_TIER
    sweep, which is noise while authoring is still in progress."""
    findings = []
    only_set = _resolve_only(only)
    for f, relparts in _iter_markdown_files(roots):
        if only_set is not None:
            try:
                if f.resolve() not in only_set:
                    continue
            except OSError:
                continue
        try:
            size = f.stat().st_size
        except OSError:
            continue
        if size > _MAX_DOC_BYTES:
            findings.append(
                ("warn", "FILE_TOO_LARGE", str(f), 1, "%d bytes; skipped content checks" % size)
            )
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings += _check_links(f, text, roots)
        findings += _check_tables(f, text)
        findings += _check_placeholders(f, text, coverage is not None)
        findings += _check_forbidden(f, text, forbidden)
        findings += _check_unresolved_command(f, text, captures_dir)
        findings += _check_leaked_paths(f, text)
        findings += _check_adr(f, text, relparts)
        # Grounding and showcase both ASK FOR AN EDIT, so both stop at the frozen tier.
        if not _is_frozen_tier(relparts):
            findings += _check_grounding(f, text, captures_dir)
            findings += _check_showcase(f, text, relparts)
    if tier_check:
        findings += _check_empty_tier(roots, coverage)
    has_error = any(sev == "error" for sev, *_ in findings)
    return findings, (1 if has_error else 0)


# --- CLI verbs -----------------------------------------------------------------


def cmd_redact(rest, prog="check.py"):
    """`redact <raw_file> --home H --user U --stamp S [--extra a,b]` -> stdout."""

    def _usage_p(m):
        return _usage(m, prog)

    raw_file, home, user, stamp, extra = None, None, None, None, []
    it = iter(rest)
    for a in it:
        if a in ("--home", "--user", "--stamp", "--extra"):
            value = next(it, _MISSING)
            if value is _MISSING:
                return _usage_p("ERROR: %s needs a value" % a)
            if a == "--home":
                home = value
            elif a == "--user":
                user = value
            elif a == "--stamp":
                stamp = value
            else:
                extra = [t for t in value.split(",") if t]
        elif raw_file is None:
            raw_file = a
        else:
            return _usage_p(_REDACT_USAGE)
    if raw_file is None:
        return _usage_p(_REDACT_USAGE)
    # --home/--user/--stamp are documented as REQUIRED and are now enforced. They
    # defaulted to "" silently, so `redact cap.txt` echoed the capture back verbatim
    # and exited 0 -- a privacy gate reporting success having redacted nothing. The
    # partial form was worse: `--home` last swallowed the end of argv, so user and
    # stamp were stripped and the home path was not, and the result is indistinguishable
    # from a clean run. This output gets committed.
    absent = [n for n, v in (("--home", home), ("--user", user), ("--stamp", stamp)) if v is None]
    if absent:
        return _usage_p("ERROR: redact requires " + ", ".join(absent) + "\n" + _REDACT_USAGE)
    text = pathlib.Path(raw_file).read_text(encoding="utf-8")
    sys.stdout.write(redact_output(text, home, user, stamp, extra))
    return 0


def cmd_check_instructions(rest, prog="check.py"):
    """`check-instructions <roots...> [--repo-root DIR]...` -> findings on stdout."""

    def _usage_p(m):
        return _usage(m, prog)

    # Ground the claims in .claude/rules and .claude/skills. Read-only.
    roots, bases = [], []
    it = iter(rest)
    for a in it:
        if a == "--repo-root":
            # A missing value silently became "." -- so `--repo-root` in last position
            # resolved citations against the cwd instead of the base the operator meant,
            # turning a real UNRESOLVED_CITATION into a clean exit 0.
            value = next(it, _MISSING)
            if value is _MISSING:
                return _usage_p("ERROR: --repo-root needs a value")
            bases.append(value or ".")
        else:
            roots.append(a)
    if not roots:
        return _usage_p("usage: check.py check-instructions <roots...> [--repo-root DIR]...")
    if any(r == "" for r in roots):
        return _usage_p("ERROR: empty root (an unset shell variable?)")
    # --repo-root is REPEATABLE and defaults to the cwd. One instruction
    # file legitimately cites against two bases -- repo-root paths like
    # AGENTS.md:21 alongside source-root ones like Domain/Models/Result.cs:7
    # -- so with a single base whichever convention loses is reported as
    # unresolved. A citation resolving under ANY base counts as resolved.
    resolved_bases = []
    for b in bases or ["."]:
        p = pathlib.Path(b)
        if not p.is_dir():
            return _usage_p("ERROR: not a directory: " + b)
        resolved_bases.append(p)

    _basename_index = {}

    def _build_index():
        # Built once, on the first bare-filename citation, so a corpus that
        # only cites full paths never pays for the walk.
        for base in resolved_bases:
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                if _is_skipped(base, path):
                    continue
                _basename_index.setdefault(path.name, []).append(path)

    def _long_enough(target, line_number):
        try:
            with target.open(encoding="utf-8", errors="replace") as fh:
                return sum(1 for _ in fh) >= line_number
        except OSError:
            return False

    def _resolve(rel, line_number):
        # A citation resolves when the file exists under some base AND is
        # long enough to have the cited line. Anything unreadable counts as
        # unresolved rather than raising: one bad citation must not abort.
        for base in resolved_bases:
            target = base / rel
            if target.is_file() and _long_enough(target, line_number):
                return True
        # Citations are routinely written as shorthand -- a bare filename
        # (`onboard_lib.py:168`) or a partial path
        # (`templates/update-docs/SKILL.md:207`) -- and a reader resolves
        # them from context, so the checker accepts any file whose path ENDS
        # with the cited one. Validated on two corpora: strict-only matching
        # reported 50 errors in one documentation tree and 1 in a backend
        # repository, and every one was a correct citation in shorthand.
        # What survives the fallback is the finding worth having -- a path
        # naming no file at all, or a line past the end of the file it names.
        if not _basename_index:
            _build_index()
        want = tuple(rel.split("/"))
        return any(
            cand.parts[-len(want) :] == want and _long_enough(cand, line_number)
            for cand in _basename_index.get(want[-1], ())
        )

    files = []
    for root in roots:
        p = pathlib.Path(root)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(p.rglob("*.md")))
        else:
            return _usage_p("ERROR: not found: " + root)

    # Repo file list, relative to each base, for DEAD_GLOB. Built once and
    # only when a paths: entry actually needs it.
    _repo_files = []

    def _glob_matches(glob):
        if not _repo_files:
            for base in resolved_bases:
                for path in base.rglob("*"):
                    if path.is_file() and not _is_skipped(base, path):
                        _repo_files.append(path.relative_to(base).as_posix())
            if not _repo_files:
                _repo_files.append("")  # sentinel: walked, found nothing
        # Translate the glob to a regex: ** spans separators, * does not.
        out, i = "", 0
        while i < len(glob):
            if glob.startswith("**/", i):
                out += "(?:.*/)?"
                i += 3
            elif glob.startswith("**", i):
                out += ".*"
                i += 2
            elif glob[i] == "*":
                out += "[^/]*"
                i += 1
            elif glob[i] == "?":
                out += "[^/]"
                i += 1
            else:
                out += re.escape(glob[i])
                i += 1
        rx = re.compile("^" + out + "$")
        return sum(1 for p in _repo_files if rx.match(p))

    # Script names per runner, for UNDEFINED_SCRIPT. A runner whose manifest is
    # absent stays OUT of the mapping, which skips it rather than reporting
    # every citation as undefined -- and keeps a PHP repo's composer scripts
    # from being checked against an npm script list.
    def _manifest_scripts(filename):
        for base in resolved_bases:
            manifest = base / filename
            if not manifest.is_file():
                continue
            try:
                return set(json.loads(manifest.read_text(encoding="utf-8")).get("scripts", {}))
            except (ValueError, OSError):
                return None
        return None

    _scripts = {}
    for _runner, _manifest in (("npm", "package.json"), ("composer", "composer.json")):
        _found = _manifest_scripts(_manifest)
        if _found is not None:
            _scripts[_runner] = _found
    if not _scripts:
        _scripts = None

    def _kind_of(path):
        # MISSING_PATHS applies to rules only. A skill without paths: is
        # normal -- it loads when invoked, not when a file is read.
        parts = path.parts
        if "rules" in parts:
            return "rule"
        if "skills" in parts or path.name == "SKILL.md":
            return "skill"
        return None

    findings, code = [], 0
    for f in files:
        for sev, fcode, lineno, detail in check_instructions(
            f.read_text(encoding="utf-8", errors="replace"),
            _resolve,
            kind=_kind_of(f),
            glob_matches=_glob_matches,
            known_scripts=_scripts,
        ):
            findings.append((sev, fcode, str(f), lineno, detail))
            if sev == "error":
                code = 1
    for sev, fcode, fpath, lineno, detail in findings:
        sys.stdout.write("%s\t%s\t%s:%d\t%s\n" % (sev.upper(), fcode, fpath, lineno, detail))
    return code


def cmd_check_docs(rest, prog="check.py"):
    """`check-docs <roots...> [--captures DIR] [--coverage FILE] ...` -> findings."""

    def _usage_p(m):
        return _usage(m, prog)

    roots, captures_dir, coverage_file, forbidden = [], None, None, []
    only, tier_check = [], True
    it = iter(rest)
    for a in it:
        if a in ("--captures", "--coverage", "--forbidden", "--only"):
            value = next(it, _MISSING)
            if value is _MISSING:
                return _usage_p("ERROR: %s needs a value" % a)
            if a == "--captures":
                captures_dir = value
            elif a == "--coverage":
                coverage_file = value
            elif a == "--forbidden":
                forbidden = [t for t in value.split(",") if t]
            else:
                only.append(value)
        elif a == "--no-tier-check":
            tier_check = False
        else:
            roots.append(a)
    if not roots:
        return _usage_p(
            "usage: check.py check-docs <roots...> "
            "[--captures DIR] [--coverage FILE] [--forbidden a,b] "
            "[--only PATH]... [--no-tier-check]"
        )
    # A root that does not exist is a USAGE error, not an empty scan. check-docs used
    # to skip it silently and exit 0, so the stamped recipe's unresolved `<index>`
    # placeholder -- quoted, as a careful operator would -- reported a clean tree while
    # never opening the index doc at all. A gate that passes by scanning nothing is
    # worse than a missing gate, because it produces evidence. `check-instructions`
    # already failed closed here; this makes the two verbs agree.
    # An empty-string root is `Path(".")`, which exists -- so an unset `$DOCS` used to
    # scan the whole cwd instead of erroring.
    if any(r == "" for r in roots):
        return _usage_p("ERROR: empty root (an unset shell variable?)")
    missing = [r for r in roots if not pathlib.Path(r).exists()]
    if missing:
        return _usage_p("ERROR: not found: " + ", ".join(missing))
    # `--only` had the same silent-pass shape the root guard closed, one flag over: the
    # paths are only `.resolve()`d, which never fails, so a typo -- or the quoted
    # `<index>` placeholder itself -- scoped reporting to the empty set and exited 0
    # while the unscoped scan of the same tree exited 1.
    only_missing = [o for o in only if not pathlib.Path(o).exists()]
    if only_missing:
        return _usage_p("ERROR: --only path not found: " + ", ".join(only_missing))
    if captures_dir is not None and not pathlib.Path(captures_dir).is_dir():
        return _usage_p("ERROR: --captures dir not found: " + captures_dir)
    if coverage_file is not None and not pathlib.Path(coverage_file).is_file():
        return _usage_p("ERROR: --coverage file not found: " + coverage_file)
    # Parse the coverage record HERE, in its own guard, so a malformed
    # JSON error reports accurately and is NOT masked as a usage-2 by the
    # broad manifest handler below (review I2 / spec 4.2).
    try:
        coverage = _load_coverage(coverage_file)
    except (ValueError, OSError):
        return _usage_p("ERROR: malformed coverage record: " + str(coverage_file))
    findings, code = _check_docs(
        roots, captures_dir, coverage, forbidden, only=only, tier_check=tier_check
    )
    for sev, fcode, fpath, lineno, detail in findings:
        sys.stdout.write("%s\t%s\t%s:%d\t%s\n" % (sev.upper(), fcode, fpath, lineno, detail))
    return code


def main(argv):
    if not argv:
        return _usage(__doc__.split("Usage:", 1)[1].strip())
    cmd, rest = argv[0], argv[1:]
    return run(cmd, rest)


def run(cmd, rest, prog="check.py"):
    """Dispatch one verb, with the error handling that belongs to it.

    onboard.py delegates HERE rather than to `cmd_*` directly, so both entry points
    share one handler and cannot report the same failure differently. They did: a
    capture with a decode error printed `ERROR: malformed input: …` through check.py
    and `ERROR: malformed manifest: …` through onboard.py, because the delegated call
    sat inside onboard.py's own except clause and never reached this one. Identical by
    construction beats identical by coincidence -- a parity test can only catch the
    inputs it happens to try, and the first sweep for this used parse errors, not
    decode errors, and found nothing.
    """
    try:
        if cmd == "check-docs":
            return cmd_check_docs(rest, prog=prog)
        if cmd == "check-instructions":
            return cmd_check_instructions(rest, prog=prog)
        if cmd == "redact":
            return cmd_redact(rest, prog=prog)
    except OSError as exc:  # missing/unreadable file -> clean exit 2
        sys.stderr.write("ERROR: " + str(exc) + "\n")
        return 2
    except (ValueError, KeyError) as exc:
        sys.stderr.write("ERROR: malformed input: " + str(exc) + "\n")
        return 2
    return _usage("unknown command: " + cmd, prog)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
