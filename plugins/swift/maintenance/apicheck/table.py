"""Render the generated platform table in references/platform-availability.md."""

from __future__ import annotations

from .apple import PLATFORMS, Availability

BEGIN = "<!-- BEGIN GENERATED: maintenance/check-apis.py --write-table -->"
END = "<!-- END GENERATED -->"
DOC_URL = "https://developer.apple.com/documentation/"


def render_table(rows: list[tuple[str, str, dict[str, Availability]]]) -> str:
    """rows: (name, doc path, platforms). A cell holds the introduced version, or — where the API is missing."""
    lines = [
        "| API | " + " | ".join(PLATFORMS) + " | Notes |",
        "|---|" + "---|" * len(PLATFORMS) + "---|",
    ]
    for name, path, platforms in rows:
        cells, beta, deprecated = [], [], {}
        for platform in PLATFORMS:
            a = platforms.get(platform)
            if a is None or a.unavailable:
                cells.append("—")
                continue
            cells.append(a.introduced or "?")
            if a.beta:
                beta.append(platform)
            if a.deprecated_at:
                deprecated.setdefault(a.deprecated_at, []).append(platform)
        notes = [f"beta: {', '.join(beta)}"] if beta else []
        notes += [
            f"deprecated {version}: {', '.join(names)}"
            for version, names in deprecated.items()
        ]
        notes.append(f"<{DOC_URL}{path}>")
        lines.append(
            f"| `{name}` | " + " | ".join(cells) + " | " + "; ".join(notes) + " |"
        )
    return "\n".join(lines)


def replace_block(text: str, table: str) -> str:
    """Swap the text between the BEGIN/END markers for the table; refuse unless there is exactly one pair, in order."""
    if (
        text.count(BEGIN) != 1
        or text.count(END) != 1
        or text.index(BEGIN) > text.index(END)
    ):
        raise ValueError(f"need exactly one {BEGIN!r} followed by one {END!r}")
    head, rest = text.split(BEGIN)
    _, tail = rest.split(END)
    return f"{head}{BEGIN}\n{table}\n{END}{tail}"
