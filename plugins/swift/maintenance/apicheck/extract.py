"""Find API-shaped names in the skills' Markdown: .name( calls, Capitalised identifiers, @Attributes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SWIFT_FENCES = frozenset({"", "swift"})
BUILTIN_IGNORES = frozenset({"Self", "Type", "Protocol", "Any"})

_FENCE = re.compile(
    r"^([ \t]{0,4})(```|~~~)[ \t]*([^\n]*)\n(.*?)^\1\2[ \t]*$", re.M | re.S
)
_INLINE = re.compile(r"`([^`\n]+)`")
_TRIPLE_STRING = re.compile(r'"""(?:.|\n)*?"""')
_STRING = re.compile(r'"(?:\\.|[^"\\\n])*"')
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"//[^\n]*")
_DIRECTIVE = re.compile(r"^[ \t]*#(?:if|elseif|else|endif)\b[^\n]*", re.M)
_IMPORT = re.compile(r"^[ \t]*(?:@testable[ \t]+)?import[ \t]+[^\n]*", re.M)
_MEMBER = re.compile(r"\.([a-z]\w*)\(")
_RECEIVER = re.compile(r"(\w+)[?!]*$")
_SIGNATURE = re.compile(r"\.?([a-z]\w*)\((?:\w*:)*\)")
_TYPE = re.compile(r"(?<![@\w])([A-Z][A-Za-z0-9_]*)\b")
_ATTRIBUTE = re.compile(r"@([A-Z]\w*)")
_DECL = re.compile(
    r"\b(?:struct|class|enum|protocol|actor|typealias|associatedtype|func|var|let|case)\s+([A-Za-z_]\w*)"
)
_GENERIC_DECL = re.compile(
    r"\b(?:struct|class|enum|actor|protocol|func|init|typealias)\b[^<{(\n]*<([^<>]*)>"
)


@dataclass(frozen=True)
class Name:
    text: str
    kind: str  # "member" (.name( call or name(_:) span), "type" (Capitalised) or "attribute" (@Name)


def strip_code(code: str) -> str:
    """Drop string literals, comments, #if lines and import lines so only code remains."""
    code = _TRIPLE_STRING.sub('""', code)
    code = _STRING.sub('""', code)
    code = _BLOCK_COMMENT.sub(" ", code)
    code = _LINE_COMMENT.sub("", code)
    code = _DIRECTIVE.sub("", code)
    return _IMPORT.sub("", code)


def code_fragments(markdown: str) -> list[str]:
    """Swift code from fenced blocks (info string empty or starting with "swift") and from inline spans."""
    fragments = []

    def take_fence(match: re.Match) -> str:
        info = match.group(3).split()
        if (info[0].lower() if info else "") in SWIFT_FENCES:
            indent, body = match.group(1), match.group(4)
            if indent:
                body = re.sub(f"^{re.escape(indent)}", "", body, flags=re.M)
            fragments.append(strip_code(body))
        return "\n"

    prose = _FENCE.sub(take_fence, markdown)
    fragments.extend(strip_code(span) for span in _INLINE.findall(prose))
    return fragments


def _members(code: str):
    for match in _MEMBER.finditer(code):
        receiver = _RECEIVER.search(code, max(0, match.start() - 80), match.start())
        if receiver and not receiver.group(1)[0].isupper():
            continue  # a call on a variable, e.g. model.load(
        yield match.group(1)


def names_in(fragment: str) -> set[Name]:
    found = {Name(n, "member") for n in _members(fragment)}
    signature = _SIGNATURE.fullmatch(fragment.strip())
    if signature:
        found.add(Name(signature.group(1), "member"))
    found |= {Name(n, "attribute") for n in _ATTRIBUTE.findall(fragment)}
    found |= {Name(n, "type") for n in _TYPE.findall(fragment) if len(n) > 1}
    return found


def declared_names(fragments: list[str]) -> set[str]:
    """Names the snippets themselves declare: types, functions, properties, cases, generic parameters."""
    declared = set()
    for code in fragments:
        declared.update(_DECL.findall(code))
        for params in _GENERIC_DECL.findall(code):
            for part in params.split(","):
                ident = part.split(":")[0].strip()
                if ident.isidentifier():
                    declared.add(ident)
    return declared


def scan(root: Path) -> dict[Name, list[Path]]:
    """Every API-shaped name in root/**/*.md → the files that use it, minus names a file declares itself."""
    found: dict[Name, list[Path]] = {}
    for md in sorted(root.rglob("*.md")):
        fragments = code_fragments(md.read_text(encoding="utf-8"))
        declared = declared_names(fragments)
        names = set().union(*(names_in(f) for f in fragments))
        for name in sorted(names, key=lambda n: (n.text, n.kind)):
            if name.text not in declared and name.text not in BUILTIN_IGNORES:
                found.setdefault(name, []).append(md)
    return found
