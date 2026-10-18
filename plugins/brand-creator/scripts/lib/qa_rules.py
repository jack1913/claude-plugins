"""qa/rules.json: the owner-adjustable thresholds of the QA checks, with proposals as defaults.

The numbers here are the agent's proposals (G4: each is a one-line, revertable "(rule)" item). A project overrides any
of them in `<project>/qa/rules.json`; every report says whether a value is the proposal or the project's own. Unknown
keys are refused (a typo must not silently fall back to the default).

    {"schema": 1,
     "downscale": {"accent_min_px": 4, "accent_rule_max_size": 32, "accent_colour": "color.accent", "accent_tolerance": 40},
     "states":    {"greyscale_min_diff": 0.10, "silhouette_min_diff": 0.10, "ground": "#808080"},
     "cvd":       {"min_delta_e": 10.0, "deficiencies": ["protan", "deutan", "tritan"]},
     "guides":    {"tolerance_px": 1.5},
     "family":    {"tile_share_tolerance": 0.05},
     "bands":     [{"name": "small", "max_px": 32, "drawing": "assets/logo/grid-mark.svg"},
                   {"name": "large", "drawing": "assets/logo/mark.svg"}]}
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from _common import EXIT_USAGE, fail

RULES_FILE = "qa/rules.json"

DEFAULTS: dict = {
    "downscale": {
        "accent_min_px": 4,            # the accent must contain a solid square of at least this many px ...
        "accent_rule_max_size": 32,    # ... at this size and below
        "accent_colour": "color.accent",  # a token role (resolved in tokens.json) or #rrggbb
        "accent_tolerance": 40,        # RGB distance within which a pixel still counts as the accent
    },
    "states": {"greyscale_min_diff": 0.10, "silhouette_min_diff": 0.10, "ground": "#808080"},
    "cvd": {"min_delta_e": 10.0, "deficiencies": ["protan", "deutan", "tritan"]},
    "guides": {"tolerance_px": 1.5},
    "family": {"tile_share_tolerance": 0.05},
    "bands": [],
}
_NUM = (int, float)


def _check(section: str, key: str, value, default) -> None:
    if isinstance(default, bool) or not isinstance(default, (int, float, str, list)):
        return
    ok = (isinstance(value, _NUM) and not isinstance(value, bool)) if isinstance(default, _NUM) else isinstance(value, type(default))
    if not ok:
        fail(EXIT_USAGE, f"{RULES_FILE}: {section}.{key} must be a {type(default).__name__}, got {value!r}")
    if isinstance(default, _NUM) and value <= 0:
        fail(EXIT_USAGE, f"{RULES_FILE}: {section}.{key} must be above 0, got {value!r}")


def validate_bands(bands) -> list[dict]:
    if not isinstance(bands, list):
        fail(EXIT_USAGE, f"{RULES_FILE}: bands must be a list")
    out, prev = [], 0
    for i, b in enumerate(bands):
        if not (isinstance(b, dict) and isinstance(b.get("name"), str) and b["name"].strip()
                and isinstance(b.get("drawing"), str) and b["drawing"].strip()):
            fail(EXIT_USAGE, f"{RULES_FILE}: bands[{i}] needs a name and a drawing (a path inside the project)")
        extra = set(b) - {"name", "max_px", "drawing", "note"}
        if extra:
            fail(EXIT_USAGE, f"{RULES_FILE}: bands[{i}] has unknown keys {sorted(extra)}")
        last = i == len(bands) - 1
        mx = b.get("max_px")
        if mx is None and not last:
            fail(EXIT_USAGE, f"{RULES_FILE}: only the last band may omit max_px (it covers every larger size)")
        if mx is not None:
            if not isinstance(mx, int) or isinstance(mx, bool) or mx <= prev:
                fail(EXIT_USAGE, f"{RULES_FILE}: bands[{i}].max_px must be a whole number above the previous band's ({prev})")
            prev = mx
        out.append({"name": b["name"].strip(), "max_px": mx, "drawing": b["drawing"].strip(), "note": b.get("note", "")})
    if len({b["name"] for b in out}) != len(out):
        fail(EXIT_USAGE, f"{RULES_FILE}: band names must be unique")
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
        if sec == "bands":
            rules["bands"] = validate_bands(val)
            rules["_from_file"].append("bands")
            continue
        if not isinstance(val, dict):
            fail(EXIT_USAGE, f"{RULES_FILE}: {sec} must be an object")
        for k, v in val.items():
            if k not in DEFAULTS[sec]:
                fail(EXIT_USAGE, f"{RULES_FILE}: unknown key {sec}.{k} (known: {', '.join(DEFAULTS[sec])})")
            _check(sec, k, v, DEFAULTS[sec][k])
            rules[sec][k] = v
            rules["_from_file"].append(f"{sec}.{k}")
    return rules, RULES_FILE


def pick_band(bands: list[dict], size_px: int) -> dict | None:
    """The one function that picks the drawing for a body size: the first band whose max_px covers it (None when no bands)."""
    for b in bands:
        if b["max_px"] is None or size_px <= b["max_px"]:
            return b
    return None
