"""qa/rules.json: the owner-adjustable thresholds of the QA checks, with proposals as defaults.

The numbers here are the agent's proposals (G4: each is a one-line, revertable "(rule)" item). A project overrides any
of them in `<project>/qa/rules.json`; every report says whether a value is the proposal or the project's own. Unknown
keys are refused (a typo must not silently fall back to the default).

    {"schema": 1,
     "downscale": {"accent_min_px": 4, "accent_rule_max_size": 32, "accent_colour": "color.accent", "accent_tolerance": 40,
                   "exemptions": [{"source": "assets/logo/mark-16.svg", "max_px": 16, "reason": "..."}]},
     "states":    {"greyscale_min_diff": 0.10, "silhouette_min_diff": 0.10, "ground": "#808080"},
     "cvd":       {"min_delta_e": 10.0, "deficiencies": ["protan", "deutan", "tritan"]},
     "guides":    {"tolerance_px": 1.5},
     "family":    {"tile_share_tolerance": 0.05},
     "favicon":   {"drawing": "assets/logo/favicon.svg"},
     "bands":     [{"name": "small", "max_px": 32, "drawing": "assets/logo/grid-mark.svg"},
                   {"name": "large", "drawing": "assets/logo/mark.svg"}]}

A project with several marks (a family of products that share one system) lists them in `marks` instead, each with its own
bands; the top-level bands and favicon.drawing then stay empty, and every tool that draws a mark takes --mark <id>:

    {"schema": 1,
     "marks": {"tool-a": {"bands": [{"name": "small", "max_px": 16, "drawing": "assets/logo/tool-a-16.svg"},
                                    {"name": "large", "drawing": "assets/logo/tool-a.svg"}],
                          "name": "Tool A", "favicon": "", "accent": "color.tool-a", "tagline": "tool-a one-liner"},
               "tool-b": {"bands": [{"name": "all", "drawing": "assets/logo/tool-b.svg"}]}}}

The last band's drawing is the mark's main drawing. name (default: the id) is what cards say when there is no drawn lettering,
accent a token role for the cards' accent and for the accent `downscale` measures on its drawings and its packs' files (default:
color.accent on cards, downscale.accent_colour in downscale), tagline a FACTS.md label whose value goes under the name.
"""
from __future__ import annotations

import copy
import json
import posixpath
import re
from pathlib import Path

from _common import EXIT_USAGE, fail

RULES_FILE = "qa/rules.json"

DEFAULTS: dict = {
    "downscale": {
        "accent_min_px": 4,            # the accent must contain a solid square of at least this many px ...
        "accent_rule_max_size": 32,    # ... at this size and below
        "accent_colour": "color.accent",  # a token role (resolved in tokens.json) or #rrggbb
        "accent_tolerance": 40,        # RGB distance within which a pixel still counts as the accent
        "exemptions": [],              # misses the owner accepts: {"source": <master>, "max_px": <size>, "reason": <why>}
    },
    "states": {"greyscale_min_diff": 0.10, "silhouette_min_diff": 0.10, "ground": "#808080"},
    "cvd": {"min_delta_e": 10.0, "deficiencies": ["protan", "deutan", "tritan"]},
    "guides": {"tolerance_px": 1.5},
    "family": {"tile_share_tolerance": 0.05},
    "favicon": {"drawing": ""},        # icon.svg's drawing; empty = the band rule's drawing for a browser tab (the smallest favicon layer)
    "bands": [],
    "marks": {},                       # several marks, each with its own bands (see the docstring); empty = one mark
}
_NUM = (int, float)
MARK_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")   # names folders and reports: assets/<pack>/<id>/, emit-<pack>/<id>.json
MARK_KEYS = ("bands", "name", "favicon", "accent", "tagline")


def _check(section: str, key: str, value, default) -> None:
    if isinstance(default, bool) or not isinstance(default, (int, float, str, list)):
        return
    ok = (isinstance(value, _NUM) and not isinstance(value, bool)) if isinstance(default, _NUM) else isinstance(value, type(default))
    if not ok:
        fail(EXIT_USAGE, f"{RULES_FILE}: {section}.{key} must be a {type(default).__name__}, got {value!r}")
    if isinstance(default, _NUM) and value <= 0:
        fail(EXIT_USAGE, f"{RULES_FILE}: {section}.{key} must be above 0, got {value!r}")


def validate_bands(bands, where: str = "bands") -> list[dict]:
    if not isinstance(bands, list):
        fail(EXIT_USAGE, f"{RULES_FILE}: {where} must be a list")
    out, prev = [], 0
    for i, b in enumerate(bands):
        if not (isinstance(b, dict) and isinstance(b.get("name"), str) and b["name"].strip()
                and isinstance(b.get("drawing"), str) and b["drawing"].strip()):
            fail(EXIT_USAGE, f"{RULES_FILE}: {where}[{i}] needs a name and a drawing (a path inside the project)")
        extra = set(b) - {"name", "max_px", "drawing", "note"}
        if extra:
            fail(EXIT_USAGE, f"{RULES_FILE}: {where}[{i}] has unknown keys {sorted(extra)}")
        last = i == len(bands) - 1
        mx = b.get("max_px")
        if mx is None and not last:
            fail(EXIT_USAGE, f"{RULES_FILE}: only the last band may omit max_px (it covers every larger size)")
        if mx is not None:
            if not isinstance(mx, int) or isinstance(mx, bool) or mx <= prev:
                fail(EXIT_USAGE, f"{RULES_FILE}: {where}[{i}].max_px must be a whole number above the previous band's ({prev})")
            prev = mx
        if mx is not None and last:
            fail(EXIT_USAGE, f"{RULES_FILE}: the last band covers every larger size, so it has no max_px ({where}[{i}] stops at {mx} px, "
                             f"and nothing would draw a larger size)")
        out.append({"name": b["name"].strip(), "max_px": mx, "drawing": b["drawing"].strip(), "note": b.get("note", "")})
    if len({b["name"] for b in out}) != len(out):
        fail(EXIT_USAGE, f"{RULES_FILE}: band names must be unique ({where})")
    return out


def validate_marks(marks) -> dict[str, dict]:
    """marks: {id: {bands, name?, favicon?, accent?, tagline?}} -> {id: entry with every key}. Each mark needs at least one band."""
    if not isinstance(marks, dict):
        fail(EXIT_USAGE, f"{RULES_FILE}: marks must be an object of mark id to its entry")
    out = {}
    for mid, m in marks.items():
        where = f"marks.{mid}"
        if not MARK_ID.fullmatch(mid):
            fail(EXIT_USAGE, f"{RULES_FILE}: {where}: a mark id is lower-case letters and digits joined by hyphens (it names folders and reports)")
        if not isinstance(m, dict):
            fail(EXIT_USAGE, f"{RULES_FILE}: {where} must be an object")
        extra = set(m) - set(MARK_KEYS)
        if extra:
            fail(EXIT_USAGE, f"{RULES_FILE}: {where} has unknown keys {sorted(extra)} (known: {', '.join(MARK_KEYS)})")
        if not m.get("bands"):
            fail(EXIT_USAGE, f"{RULES_FILE}: {where}.bands: every mark names its drawing for each size (at least one band; the last one has no max_px)")
        entry = {"id": mid, "bands": validate_bands(m["bands"], f"{where}.bands")}
        for k in ("name", "favicon", "accent", "tagline"):
            v = m.get(k, "")
            if not isinstance(v, str):
                fail(EXIT_USAGE, f"{RULES_FILE}: {where}.{k} must be a string, got {v!r}")
            entry[k] = v.strip()
        entry["name"] = entry["name"] or mid
        out[mid] = entry
    return out


def validate_exemptions(items) -> list[dict]:
    """downscale.exemptions: each a miss the owner accepts for one master at a size and below, with the reason in words."""
    if not isinstance(items, list):
        fail(EXIT_USAGE, f"{RULES_FILE}: downscale.exemptions must be a list")
    out = []
    for i, e in enumerate(items):
        where = f"{RULES_FILE}: downscale.exemptions[{i}]"
        if not isinstance(e, dict):
            fail(EXIT_USAGE, f"{where} must be an object with source, max_px and reason")
        extra = set(e) - {"source", "max_px", "reason"}
        if extra:
            fail(EXIT_USAGE, f"{where} has unknown keys {sorted(extra)}")
        src, mx, why = e.get("source"), e.get("max_px"), e.get("reason")
        if not (isinstance(src, str) and src.strip()) or src.strip().startswith("/") or ".." in Path(src.strip()).parts:
            fail(EXIT_USAGE, f"{where}.source must be the master's path inside the project, as downscale --source names it")
        if not isinstance(mx, int) or isinstance(mx, bool) or mx <= 0:
            fail(EXIT_USAGE, f"{where}.max_px must be a whole number above 0 (the largest size it excuses)")
        if not (isinstance(why, str) and why.strip()):
            fail(EXIT_USAGE, f"{where}.reason must say why the owner accepts the miss")
        out.append({"source": posixpath.normpath(src.strip().replace("\\", "/")), "max_px": mx, "reason": why.strip()})
    return out


def load(project: Path) -> tuple[dict, str]:
    """-> (rules, source) where source is 'proposals (no qa/rules.json)' or 'qa/rules.json'."""
    rules = copy.deepcopy(DEFAULTS)
    rules["_from_file"] = []  # dotted keys the project set itself (everything else is a proposal)
    f = project / RULES_FILE
    if not f.is_file():
        return rules, "proposals (no qa/rules.json)"
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        fail(EXIT_USAGE, f"{RULES_FILE} is not valid JSON: {e}")
    if not isinstance(doc, dict):
        fail(EXIT_USAGE, f"{RULES_FILE} must be a JSON object")
    for sec, val in doc.items():
        if sec == "schema":
            if val != 1:
                fail(EXIT_USAGE, f"{RULES_FILE}: unknown schema {val!r} (this version reads 1)")
            continue
        if sec not in DEFAULTS:
            fail(EXIT_USAGE, f"{RULES_FILE}: unknown section {sec!r} (known: {', '.join(sorted(DEFAULTS))})")
        if sec in ("bands", "marks"):
            rules[sec] = validate_bands(val) if sec == "bands" else validate_marks(val)
            rules["_from_file"].append(sec)
            continue
        if not isinstance(val, dict):
            fail(EXIT_USAGE, f"{RULES_FILE}: {sec} must be an object")
        for k, v in val.items():
            if k not in DEFAULTS[sec]:
                fail(EXIT_USAGE, f"{RULES_FILE}: unknown key {sec}.{k} (known: {', '.join(DEFAULTS[sec])})")
            _check(sec, k, v, DEFAULTS[sec][k])
            rules[sec][k] = validate_exemptions(v) if (sec, k) == ("downscale", "exemptions") else v
            rules["_from_file"].append(f"{sec}.{k}")
    if rules["marks"] and (rules["bands"] or rules["favicon"]["drawing"]):
        fail(EXIT_USAGE, f"{RULES_FILE}: with marks, each mark names its own bands and favicon; move the top-level bands and favicon.drawing into the marks")
    return rules, RULES_FILE


def mark_entry(rules: dict, mark_id: str) -> dict:
    """The entry of one mark of qa/rules.json marks; an id it does not list is a usage error naming the ids it does."""
    if mark_id not in rules["marks"]:
        listed = ", ".join(rules["marks"]) or "none: this project has one mark"
        fail(EXIT_USAGE, f"unknown mark {mark_id!r} ({RULES_FILE} marks: {listed})")
    return rules["marks"][mark_id]


def select_mark(a, rules: dict, *, required: bool = True) -> dict | None:
    """The mark this run draws: its entry in qa/rules.json marks, or None in a one-mark project. With marks, a run without --mark is a usage
    error (exit 2) unless the caller makes one thing for all the marks together (required=False); --svg and --svg-dark name one file, so they
    do not mix with marks. --mark in a one-mark project is a usage error too: nothing is guessed."""
    if not rules["marks"]:
        if a.mark:
            fail(EXIT_USAGE, f"--mark {a.mark}: this project has one mark (qa/rules.json lists no marks)")
        return None
    if getattr(a, "svg", None) or getattr(a, "svg_dark", None):
        fail(EXIT_USAGE, "--svg and --svg-dark name one mark's file, and this project lists its marks in qa/rules.json: pass --mark <id>")
    if not a.mark:
        if required:
            fail(EXIT_USAGE, f"this project has several marks ({', '.join(rules['marks'])}): pass --mark <id>")
        return None
    return mark_entry(rules, a.mark)


def bands_for(rules: dict, mark_id: str | None) -> list[dict]:
    """The size bands that decide a drawing: the mark's own (qa/rules.json marks), or the top-level bands of a one-mark project."""
    return mark_entry(rules, mark_id)["bands"] if mark_id else rules["bands"]


def master_of(entry: dict) -> str:
    """A mark's main drawing: the drawing of its last band, the one that covers every larger size."""
    return entry["bands"][-1]["drawing"]


def mark_of_drawing(rules: dict, project: Path, path: Path) -> str | None:
    """The id of the mark whose bands name this drawing (compared as resolved paths), or None."""
    want = path.resolve()
    for mid, m in rules["marks"].items():
        if any((project / b["drawing"]).resolve() == want for b in m["bands"]):
            return mid
    return None


def pick_band(bands: list[dict], size_px: int) -> dict | None:
    """The one function that picks the drawing for a body size: the first band whose max_px covers it (None when no bands)."""
    for b in bands:
        if b["max_px"] is None or size_px <= b["max_px"]:
            return b
    return None
