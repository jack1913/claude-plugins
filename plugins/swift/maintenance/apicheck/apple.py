"""Parse Apple's documentation JSON: framework navigator indexes and symbol pages."""

from __future__ import annotations

from dataclasses import dataclass

PLATFORMS = ("iOS", "iPadOS", "Mac Catalyst", "macOS", "visionOS", "watchOS", "tvOS")

TYPE_KINDS = frozenset(
    {
        "struct",
        "class",
        "enum",
        "protocol",
        "typealias",
        "associatedtype",
        "actor",
        "module",
    }
)
MEMBER_KINDS = frozenset(
    {"method", "property", "init", "case", "func", "subscript", "op"}
)
ATTRIBUTE_KINDS = TYPE_KINDS | {"macro"}
# Capitalised names can also be C-style global functions (NSLocalizedString, CGImageSourceCreateWithData).
KINDS_FOR = {
    "member": MEMBER_KINDS,
    "type": TYPE_KINDS | {"func"},
    "attribute": ATTRIBUTE_KINDS,
}

DOC_PREFIX = "/documentation/"


@dataclass(frozen=True)
class IndexEntry:
    path: str  # below /documentation/, e.g. "swiftui/view/glasseffect(_:in:)"
    kind: str  # Apple's node type: "method", "struct", "macro", ...
    deprecated: bool
    beta: bool

    @property
    def key(self) -> str:
        """Lower-cased name without arguments or disambiguation: glasseffect(_:in:) → glasseffect, webview-swift.struct → webview."""
        return self.path.rsplit("/", 1)[-1].split("(", 1)[0].split("-", 1)[0]


@dataclass(frozen=True)
class Availability:
    introduced: str | None
    deprecated_at: (
        str | None
    )  # a version, or "?" when Apple flags it deprecated without one
    beta: bool
    unavailable: bool


def parse_index(data: dict) -> list[IndexEntry]:
    """Flatten a navigator index (tutorials/data/index/<framework>) into symbol entries."""
    try:
        stack = list(data["interfaceLanguages"]["swift"])
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "not an Apple navigator index: no interfaceLanguages.swift"
        ) from exc
    entries, seen = [], set()
    while stack:
        node = stack.pop()
        stack.extend(node.get("children") or ())
        path = node.get("path")
        if not path or not path.startswith(DOC_PREFIX) or path in seen:
            continue  # group markers have no path; a symbol listed under several topics appears once
        seen.add(path)
        entries.append(
            IndexEntry(
                path=path[len(DOC_PREFIX) :],
                kind=node.get("type", ""),
                deprecated=bool(node.get("deprecated")),
                beta=bool(node.get("beta")),
            )
        )
    return entries


def build_lookup(entries: list[IndexEntry]) -> dict[str, list[IndexEntry]]:
    lookup: dict[str, list[IndexEntry]] = {}
    for entry in entries:
        lookup.setdefault(entry.key, []).append(entry)
    return lookup


def resolve(
    text: str, kind: str, lookup: dict[str, list[IndexEntry]]
) -> list[IndexEntry]:
    """Index entries a name can refer to: .name( calls → members, Capitalised → types, @Name → types and macros."""
    allowed = KINDS_FOR[kind]
    return [e for e in lookup.get(text.lower(), ()) if e.kind in allowed]


def parse_platforms(page: dict) -> dict[str, Availability]:
    """Read metadata.platforms from a symbol page (tutorials/data/documentation/<path>.json)."""
    try:
        platforms = page["metadata"]["platforms"]
    except (KeyError, TypeError) as exc:
        raise ValueError("symbol page has no metadata.platforms") from exc
    result = {}
    for p in platforms:
        result[p["name"]] = Availability(
            introduced=p.get("introducedAt"),
            deprecated_at=p.get("deprecatedAt")
            or ("?" if p.get("deprecated") else None),
            beta=bool(p.get("beta")),
            unavailable=bool(p.get("unavailable")),
        )
    return result


def check_claims(
    name: str, claims: dict, platforms: dict[str, Availability]
) -> list[str]:
    """Compare a manifest entry's recorded claims with Apple's platform data; return one line per mismatch."""
    problems = []
    for key, expected in claims.items():
        if key == "deprecated":
            actual = any(a.deprecated_at for a in platforms.values())
        elif key == "beta":
            actual = any(a.beta for a in platforms.values())
        elif key in PLATFORMS:
            a = platforms.get(key)
            if a is None or a.unavailable:
                actual = False
            elif isinstance(expected, str):
                actual = a.introduced
            else:
                actual = True
        else:
            raise ValueError(f"{name}: unknown claim {key!r}")
        if actual != expected:
            problems.append(
                f"{name}: skill says {key}={expected!r}, Apple says {actual!r}"
            )
    return problems
