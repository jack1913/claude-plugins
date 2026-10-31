"""The data of the site round: the layout references that ship with the plugin (skills/brand-creator/references/page-layouts.json).

A layout reference is keyed to what the visitor came to do and holds structure only: which part leads, the order of the parts, where the action sits
and how the page ends. A page records the one it used as <body data-layout="<id>">. `layout_problems` is the rule set the file must keep (a hex colour,
a number with a unit, a look word or the stock three-tiles-and-steps band in an item is a defect, so a reference never turns into a look or a template);
`load_layouts` reads the shipped file and returns the items by id, and stops with exit 3 naming the file when it cannot be used, because the file ships with the
plugin and a damaged install is the only way.

This folder is outside scripts/lib/, so a change here does not make every pack stale. Standard library only (plus _common for the error); no clock and no network.
The only read is the named file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from _common import EXIT_CANNOT, CliError

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
LAYOUTS_FILE = "skills/brand-creator/references/page-layouts.json"   # from the plugin root
VERSION = 1
TOP_KEYS = ("version", "$description", "how_to_use", "items")
ITEM_KEYS = ("id", "job", "leads_with", "parts", "action", "ends_with", "not_for")
ID_PATTERN = re.compile(r"[a-z][a-z0-9-]{2,31}")
MIN_ITEMS, MAX_ITEMS = 8, 12
MIN_PARTS, MAX_PARTS = 2, 8
# What an item must not hold: a layout is structure, so the look is never in it.
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_UNIT = re.compile(r"\b\d+(?:\.\d+)?\s?(?:(?:px|rem|em|pt|vh|vw)\b|%)", re.I)
_LOOK_WORD = re.compile(r"\b(?:colou?rs?|fonts?|typefaces?|serif|gradients?|shadows?)\b", re.I)
_THREE, _STEPS = re.compile(r"\bthree\b", re.I), re.compile(r"\bsteps\b", re.I)
_USE_ATTR = "data-layout"   # how_to_use must tell the author how to record the choice


def _text(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _look_problems(where: str, value: str) -> list[str]:
    out = []
    for rx, what in ((_HEX, "a hex colour"), (_UNIT, "a number with a unit"), (_LOOK_WORD, "a look word")):
        m = rx.search(value)
        if m:
            out.append(f"{where} holds {what} ({m.group(0)!r}); a layout is structure only")
    return out


def layout_problems(doc) -> list[str]:
    """What is wrong with a page-layouts document, as sentences ([] when it is sound): the shape, 8-12 items with unique ids, the exact keys of each, 2-8 parts, no look
    value (a hex colour, a number with a unit, a look word) in any item, and no parts that hold both `three` and `steps` (the stock band is a tell, not a layout)."""
    if not isinstance(doc, dict):
        return [f"{LAYOUTS_FILE} is not an object"]
    problems = []
    if set(doc) != set(TOP_KEYS):
        problems.append(f"the top-level keys are {sorted(doc)}, not {sorted(TOP_KEYS)}")
    if doc.get("version") != VERSION:
        problems.append(f"version is {doc.get('version')!r}, not {VERSION}")
    if not _text(doc.get("$description")):
        problems.append("$description is missing or empty")
    how = doc.get("how_to_use")
    if not (isinstance(how, list) and how and all(_text(h) for h in how)):
        problems.append("how_to_use is not a list of sentences")
    elif _USE_ATTR not in " ".join(how):
        problems.append(f"how_to_use does not tell the author to record the choice as {_USE_ATTR}")
    items = doc.get("items")
    if not isinstance(items, list):
        return problems + ["items is not a list"]
    if not MIN_ITEMS <= len(items) <= MAX_ITEMS:
        problems.append(f"{len(items)} items; there are {MIN_ITEMS} to {MAX_ITEMS}")
    seen: set[str] = set()
    for n, item in enumerate(items, 1):
        if not isinstance(item, dict):
            problems.append(f"item {n} is not an object")
            continue
        iid = item.get("id")
        name = iid if isinstance(iid, str) and iid else f"item {n}"
        if set(item) != set(ITEM_KEYS):
            missing, extra = sorted(set(ITEM_KEYS) - set(item)), sorted(set(item) - set(ITEM_KEYS))
            problems.append(f"{name}: " + "; ".join(p for p in (f"missing {missing}" if missing else "", f"extra {extra}" if extra else "") if p) + f" (the keys are {list(ITEM_KEYS)})")
        if not (isinstance(iid, str) and ID_PATTERN.fullmatch(iid)):
            problems.append(f"{name}: the id does not match {ID_PATTERN.pattern}")
        elif iid in seen:
            problems.append(f"{name}: the id is used twice")
        else:
            seen.add(iid)
        strings: list[tuple[str, str]] = [("id", iid)] if isinstance(iid, str) else []
        for key in ("job", "leads_with", "action", "ends_with", "not_for"):
            if key in item:
                if _text(item[key]):
                    strings.append((key, item[key]))
                else:
                    problems.append(f"{name}: {key} is not a sentence")
        parts = item.get("parts")
        if "parts" in item:
            if not (isinstance(parts, list) and MIN_PARTS <= len(parts) <= MAX_PARTS and all(_text(p) for p in parts)):
                problems.append(f"{name}: parts is not a list of {MIN_PARTS} to {MAX_PARTS} non-empty strings")
            else:
                strings += [(f"parts[{i}]", p) for i, p in enumerate(parts)]
                joined = " ".join(parts)
                if _THREE.search(joined) and _STEPS.search(joined):
                    problems.append(f"{name}: parts hold both 'three' and 'steps', the stock band; a layout is not a template")
        for key, value in strings:
            problems += _look_problems(f"{name}: {key}", value)
    return problems


def load_layouts() -> dict[str, dict]:
    """The layout references of the plugin, by id, in file order. Exit 3 naming the file when it cannot be read or has problems: it ships with the plugin."""
    try:
        doc = json.loads((PLUGIN_ROOT / LAYOUTS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CliError(EXIT_CANNOT, f"{LAYOUTS_FILE} cannot be read ({e}): reinstall the plugin") from None
    problems = layout_problems(doc)
    if problems:
        shown = "; ".join(problems[:3]) + (f"; and {len(problems) - 3} more" if len(problems) > 3 else "")
        raise CliError(EXIT_CANNOT, f"{LAYOUTS_FILE} has problems ({shown}): reinstall the plugin")
    return {item["id"]: item for item in doc["items"]}
