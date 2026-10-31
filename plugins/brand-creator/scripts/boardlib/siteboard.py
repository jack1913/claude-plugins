"""The rows of the website references board (data-board="site-refs"): a round after G4 that shows the owner groups of real sites to learn from, before any page of the site is built.

The board is an ordinary round (rounds/rN/board.html, N 2 or more), from templates/site-refs-board.html. This file holds the rows that need more than the page: the gates of the work
(refs_gate_rows: site-refs:tier, site-refs:brief, site-refs:g4, site-refs:research, site-refs:cliches-file) and the reading of brief/BRIEF.md that decides whether the project has a
site at all (brief_lists_site). The sections, the group count and the page rules are board_lint's own, with the other kinds of board. A site round (data-board="site") will add its rows here.

Whether the brief lists a site is read from the value after "Required surfaces:" in brief/BRIEF.md, against a list of English and Polish words (SITE_WORDS). A value wrapped in parentheses is the untouched
line of the template ("(site, app icon, ...)"), the owner's own words not yet written, and does not count. A brief in another language is not recognised: the owner adds the word "site" to the line.

The folder of boardlib is outside scripts/lib/, so a change here does not make every pack stale. Standard library only (plus _common and reflex); no clock and no network.
"""
from __future__ import annotations

import re
from pathlib import Path

from _common import Report, gate_recorded, read_state
import reflex

BRIEF_FILE = "brief/BRIEF.md"
CLICHES_FILE = "research/site-cliches.md"
MIN_CLICHES = 3                     # site-refs:cliches-file: items under "Avoid unless argued" that the file needs
TIERS = ("standard", "full")        # the site work is optional and runs in these tiers only
ANSWERS = ("online", "links-only", "none")   # the answers to the online-research question that count as asked (site_research: auto is not asked yet)
# What counts as "a site" on the Required surfaces line, in English and Polish: site(s), website(s), microsite(s), web page(s), landing page(s), www, strona and its forms, also typed without diacritics and the diminutive stronka (never "strong"), witryna and its forms.
SITE_WORDS = re.compile(r"\b(?:(?:web|micro)?sites?|web[\s-]?pages?|landing[\s-]?pages?|www|stron(?:a|y|e|ę|ą|ie|om|ami|ach|ka|ki|ke|kę|ką)?|witryn(?:a|y|e|ę|ą|ie|om|ami|ach)?)\b", re.I)
SURFACES_LINE = re.compile(r"^[ \t>*_-]*required[ \t]+surfaces[ \t]*\**[ \t]*:[ \t]*\**[ \t]*(.*?)[ \t\r]*$", re.I | re.M)   # "- Required surfaces: ...", also with the label in bold; spaces and tabs only, so an empty line never reads the next one


def brief_lists_site(project: Path) -> tuple[bool, str]:
    """(whether the brief lists a site, the detail that says why). Reads the first "Required surfaces:" line of brief/BRIEF.md, case-insensitively; a value wrapped in parentheses is the template line
    and does not count. The detail names the line, so the owner can see what was read."""
    brief = Path(project) / BRIEF_FILE
    if not brief.is_file():
        return False, f"{BRIEF_FILE} is missing, so the surfaces the brand needs are not known"
    m = SURFACES_LINE.search(brief.read_text(encoding="utf-8", errors="replace"))
    if m is None:
        return False, f'{BRIEF_FILE} has no "Required surfaces:" line'
    value = m.group(1).strip()
    if not value:
        return False, f"{BRIEF_FILE}: the Required surfaces line is empty"
    if value.startswith("(") and value.endswith(")"):
        return False, f"{BRIEF_FILE}: the Required surfaces line is still the template's ({value}): the owner has not named the surfaces"
    word = SITE_WORDS.search(value)
    if word is None:
        return False, f'{BRIEF_FILE}: "Required surfaces: {value}" names no site (a brief in a language other than English or Polish needs the word "site" on that line)'
    return True, f'{BRIEF_FILE}: "Required surfaces: {value}" lists a site ("{word.group(0)}")'


def refs_gate_rows(rep: Report, project: Path) -> None:
    """site-refs:tier (Standard or Full), site-refs:brief (the brief lists a site), site-refs:g4 (the system rules are approved), site-refs:research (the owner answered the online-research question)
    and site-refs:cliches-file (research/site-cliches.md has 3 or more items to avoid). The lint report lists the brief and the cliché file as inputs when they exist, so a change to either makes it stale."""
    for f in (Path(project) / BRIEF_FILE, Path(project) / CLICHES_FILE):
        if f.is_file():
            rep.inputs.append(f)
    state = read_state(project)

    tier = str(state.get("tier", "") or "").strip().lower()
    rep.add("site-refs:tier", "pass" if tier in TIERS else "fail", "the site work is Standard and Full",
            detail=f"tier: {tier}" if tier in TIERS else f"the site work is Standard and Full (this project's tier is {tier or 'missing'}): website references are not offered in the Quick tier")

    listed, why = brief_lists_site(project)
    rep.add("site-refs:brief", "pass" if listed else "fail", "the brief lists a site",
            detail=why if listed else f"the website references run only when {BRIEF_FILE} lists a site under Required surfaces, in the owner's words; ask the owner ({why})")

    g4 = gate_recorded(project, "G4")
    rep.add("site-refs:g4", "pass" if g4 else "fail", "website references come after the system rules (G4)",
            detail=f"G4: {g4}" if g4 else "website references come after the system rules (G4): record the owner's approval first (`brand-creator state --record G4 \"<decision>\"`)")

    answer = str(state.get("site_research", "") or "").strip().lower()
    rep.add("site-refs:research", "pass" if answer in ANSWERS else "fail", "the owner answered the online-research question",
            detail=f"site_research: {answer}" if answer in ANSWERS else
                   f"ask the owner the online-research question first and record it: state --set site_research=online|links-only|none (site_research is {answer or 'missing'})")

    items = reflex.cliche_items(project, rel=CLICHES_FILE)
    label = f"{CLICHES_FILE} lists {MIN_CLICHES} or more site clichés to avoid unless argued"
    if not (Path(project) / CLICHES_FILE).is_file():
        rep.add("site-refs:cliches-file", "fail", label, detail=f"{CLICHES_FILE} is missing: copy templates/site-cliches.md there and fill it from the sites opened for the references")
    elif len(items) < MIN_CLICHES:
        rep.add("site-refs:cliches-file", "fail", label,
                detail=f"{len(items)} item(s) under \"## Avoid unless argued\" in {CLICHES_FILE}, need at least {MIN_CLICHES} (a placeholder such as (...) does not count): they go into the reflex test of each hero variant")
    else:
        rep.add("site-refs:cliches-file", "pass", label, detail=f"{len(items)} items under \"## Avoid unless argued\"")
