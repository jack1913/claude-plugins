"""Platform spec rows (platform-specs.json). Emitters read sizes only through this module."""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

_SPECS = Path(__file__).with_name("platform-specs.json")
_PRINT = Path(__file__).with_name("print-regions.json")   # the print_region table: its rows join the platform rows as print-<REGION>
REQUIRED = ("surface", "sizes", "source_url", "checked", "status")


def load() -> dict:
    doc = json.loads(_SPECS.read_text(encoding="utf-8"))
    doc["rows"].update(json.loads(_PRINT.read_text(encoding="utf-8"))["rows"])
    for rid, row in doc["rows"].items():
        missing = [k for k in REQUIRED if k not in row]
        if missing or row["status"] not in ("V", "R", "U"):
            raise ValueError(f"platform-specs.json row {rid}: missing {missing} or bad status {row.get('status')!r}")
    return doc


def sizes(row_id: str) -> dict:
    return load()["rows"][row_id]["sizes"]


def row(row_id: str) -> dict:
    """The whole row (surface, sizes, source_url, checked, status, notes). An unknown id is a programming error: it raises."""
    rows = load()["rows"]
    if row_id not in rows:
        raise KeyError(f"platform-specs.json has no row {row_id!r}")
    return rows[row_id]


def stamp(row_ids: list[str], today: str) -> tuple[dict, list[str]]:
    """-> ({row_id: {status, checked, source_url, stale}}, warnings) for the rows an emitter used."""
    doc = load()
    limit = int(doc["stale_after_days"])
    now = _dt.date.fromisoformat(today)
    stamped, warnings = {}, []
    for rid in row_ids:
        row = doc["rows"][rid]
        age = (now - _dt.date.fromisoformat(row["checked"])).days
        stale = age > limit
        stamped[rid] = {"status": row["status"], "checked": row["checked"], "source_url": row["source_url"], "stale": stale}
        if row["status"] == "U":
            warnings.append(f"spec row {rid} is UNVERIFIED (status U): recheck {row['source_url']} before relying on it")
        elif row["status"] == "R":
            warnings.append(f"spec row {rid} was read from a secondary source (status R)")
        if stale:
            warnings.append(f"spec row {rid} is stale: checked {row['checked']}, {age} days ago (limit {limit})")
    return stamped, warnings


GENERATED_MARK = "<!-- GENERATED from scripts/emitters/platform-specs.json by `brand-creator specs-due --write-markdown`. Do not edit by hand; a test fails when this file and the JSON disagree. -->"


def markdown(doc: dict | None = None) -> str:
    """references/platform-specs.md: the table of every row, generated from platform-specs.json (the one source of sizes)."""
    doc = doc or load()
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")  # noqa: E731
    out = ["# Platform specs", "", GENERATED_MARK, "",
           "The sizes every emitter reads, with where each one comes from. Status: **V** re-verified at the source, **R** read from a secondary source, "
           "**U** unverified (recheck before relying on it; an emitter that uses a U or stale row says so in its report and in `assets/manifest.json`). "
           f"A row is stale when `checked` is older than {doc['stale_after_days']} days. `checked` records a person reading the source, never a script run. "
           "Re-verify every row before a release (`brand-creator specs-due`).", "",
           "## Contents", ""]
    out += [f"- [{rid}](#{rid})" for rid in doc["rows"]]
    out += ["", "## Table", "", "| row | surface | status | checked | source |", "|---|---|---|---|---|"]
    for rid, r in doc["rows"].items():
        out.append(f"| {rid} | {esc(r['surface'])} | {r['status']} | {r['checked']} | {esc(r['source_url'])} |")
    for rid, r in doc["rows"].items():
        out += ["", f"## {rid}", "", f"- Surface: {r['surface']}", f"- Status: {r['status']}, checked {r['checked']}", f"- Source: {r['source_url']}"]
        for extra in r.get("also", []):
            out.append(f"- Also: {extra}")
        out += [f"- Sizes: `{json.dumps(r['sizes'], ensure_ascii=False)}`"]
        if r.get("notes"):
            out += ["", r["notes"]]
    return "\n".join(out) + "\n"
