"""The edition path of a hand-authored book, shared by `patch` and `book chapter` / `book nbsp`: an approved edition is not edited in
place, --new-edition opens the next one, and every edit is one line under `## Edition log` in BRAND-STATE.md."""
import re
import sys
from pathlib import Path

import bookdata
from _common import EXIT_FAIL, fail, today

# What "the same space" means for a loose match: an ordinary space, a no-break space (U+00A0), a narrow no-break space (U+202F) and the
# white space a line break or an indent adds.
SPACE_ONLY = "[ \t\u00a0\u202f]+"
SPACE_CLASS = "[ \t\r\n  ]+"


def refuse_frozen(project, r: str) -> None:
    """Refuses (exit 1) a path an edit tool never writes: history/, removed-*/, a round that is no longer open, assets/_checks/.
    One copy for `patch`, `book chapter` and `book nbsp`. `r` is the path relative to the project."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from guard import round_is_open  # the hook's rule for which rounds may still be written
    parts = r.split("/")
    if parts[0] == "history" or parts[0].startswith("removed"):
        fail(EXIT_FAIL, f"{r} is frozen or kept as a backup; no edit tool writes in history/ or removed-*/")
    if parts[0] == "rounds" and len(parts) > 1 and re.fullmatch(r"r\d+", parts[1]) and not round_is_open(project, int(parts[1][1:])):
        fail(EXIT_FAIL, f"{r} is in an earlier round, which is read-only")
    if parts[:2] == ["assets", "_checks"]:
        fail(EXIT_FAIL, "reports under assets/_checks/ are written by the checks, never edited by hand")


def begin_edition(st, view: dict, new_edition: bool) -> int:
    """The edition this edit belongs to. Refuses (exit 1) an approved edition unless new_edition; with it, opens the next one and logs that."""
    state, _date = bookdata.approval(view)
    edition = view["edition"]
    if state == "approved" and not new_edition:
        fail(EXIT_FAIL, f"edition {edition} was approved (G5); an approved edition is not edited in place. Re-run with --new-edition to open "
                        f"edition {edition + 1} (it needs a new G5 approval)")
    if new_edition:
        edition += 1
        st.set("edition", edition)
        bookdata.append_to_section(st, "Edition log", f"- {today()} edition {edition}: opened (edition {edition - 1} stays as approved)")
    return edition


def log_line(st, edition: int, what: str, note: str = "") -> str:
    line = f"- {today()} edition {edition}: {what}" + (f": {note.strip()}" if note.strip() else "")
    bookdata.append_to_section(st, "Edition log", line)
    return line


def loose_pattern(old: str) -> "re.Pattern":
    """`old` as a pattern that matches the same text with any run of space, no-break space, narrow no-break space or line break
    where `old` has white space (and only there). White space at the very start or end of `old` that holds a line break is matched exactly
    (an --old-file ends in a newline: it must not take the blank line and indent after the match); at the edges without a line break, only spaces are loose."""
    lead, core, tail = re.fullmatch(r"(\s*)(.*?)(\s*)", old, re.S).groups()
    edge = lambda w: re.escape(w) if "\n" in w or "\r" in w else (SPACE_ONLY if w else "")   # noqa: E731
    return re.compile(edge(lead) + SPACE_CLASS.join(re.escape(p) for p in re.split(SPACE_CLASS, core)) + edge(tail))
