"""The adoption list as data: adoption.json (rows, progress, pins, the kept list) and the ADOPTION.md it renders.

Shared by `brand-creator adoption`, `brand-creator launch-todo` and `brand-creator check`. Standard library only. The fixed text of
ADOPTION.md (its frame and the "How this list is applied" section) is templates/ADOPTION.md; the data parts are rendered here.

Rows are numbered by position and are append-only. Progress (to do, doing, done) is stored apart from the rows, keyed by the row number, so a
row put in the middle, taken out or moved would move statuses silently. Two pins stop that: `nrows` (the row count) and `pins` (the start of
every row's identity, `repo|category|file`, keyed by number). `verify()` fails on any difference. Only `adoption survey` adds rows, at the end.
Line numbers are the survey's: they may drift, so every row also carries `find`, a content excerpt to look for.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from _common import EXIT_USAGE, CliError

FILE = "adoption.json"
DOC = "ADOPTION.md"
SCHEMA = 1
STATES = ("to do", "doing", "done")
# A line that records what another repository holds today carries this marker: `check --cascade` counts it as a record, not a leftover.
MARK = "<!-- target-repo -->"
CATEGORIES = [
    ("name", "Old name"),
    ("colour", "Old colour"),
    ("path", "Icon and logo files"),
    ("meta", "Package and platform metadata"),
    ("badge", "README badges and header images"),
    ("change", "Code change"),    # written by hand with `adoption add` (a change no search finds: logic, a platform rule); never touched by a survey
]
SURVEYED = [c for c, _l in CATEGORIES if c != "change"]
CATEGORY_LABEL = dict(CATEGORIES)
# keys that hold the old values of the target repos by design: the cascade search does not read them
TARGET_KEYS = ("find", "terms", "identifiers", "kept")


def empty(slug: str) -> dict:
    return {"schema": SCHEMA, "slug": slug, "repos": [], "terms": {"names": [], "colours": []}, "survey": {}, "nrows": 0, "pins": {},
            "rows": [], "progress": {}, "seen": {}, "kept": [], "identifiers": [], "accounting": {}}


def path(project: Path) -> Path:
    return project / FILE


def load(project: Path) -> dict | None:
    f = path(project)
    if not f.is_file():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def dumps(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def pin_of(row: dict) -> str:
    return f"{row['repo']}|{row['category']}|{row['file']}"


def status_of(doc: dict, n: int) -> str:
    return doc["progress"].get(str(n), STATES[0])


def counts(doc: dict) -> dict[str, int]:
    return {s: sum(1 for r in doc["rows"] if status_of(doc, r["n"]) == s) for s in STATES}


def seen_of(doc: dict, row: dict) -> dict:
    return doc["seen"].get(str(row["n"])) or {"hits": len(row.get("lines", [])), "lines": row.get("lines", [])}


def totals(doc: dict) -> dict:
    """Numbers for the sentences: matching lines (files counted for path rows) in the rows and in the kept list, files and repos."""
    row_hits = sum(seen_of(doc, r)["hits"] for r in doc["rows"] if r["category"] in ("name", "colour", "meta", "badge"))
    row_files = sum(seen_of(doc, r)["hits"] for r in doc["rows"] if r["category"] == "path")
    files = {(r["repo"], r["file"]) for r in doc["rows"] if r["category"] in ("name", "colour", "meta", "badge")}
    kept_lines = sum(k["hits"] for k in doc["kept"])
    kept_files = {(k["repo"], k["file"]) for k in doc["kept"]}
    return {"row_lines": row_hits, "icon_files": row_files, "files": len(files), "kept_lines": kept_lines, "kept_files": len(kept_files),
            "repos": len({r["repo"] for r in doc["rows"]})}


def headline(doc: dict) -> str:
    c = counts(doc)
    n = sum(c.values())
    if n == 0:
        return "nothing to adopt"
    if c["done"] == n:
        return "applied"
    if c["done"] == 0 and c["doing"] == 0:
        return "not started"
    return "in progress"


def sentence(doc: dict) -> str:
    c, t = counts(doc), totals(doc)
    n = sum(c.values())
    s = (f"{c['done']} of {n} rows done, {c['doing']} doing, {c['to do']} to do. "
         f"The survey found {t['row_lines']} matching lines in {t['files']} files and {t['icon_files']} icon and logo files across {t['repos']} "
         f"repositories; {t['kept_lines']} more lines in {t['kept_files']} files are kept, not counted.")
    gone = [r["n"] for r in doc["rows"] if r["category"] in SURVEYED and doc["seen"].get(str(r["n"])) and doc["seen"][str(r["n"])]["hits"] == 0]
    hand = sum(1 for r in doc["rows"] if r["category"] == "change")
    if hand:
        s += f" {hand} row(s) are code changes written by hand."
    if gone:
        s += f" {len(gone)} row(s) match nothing at the last survey."
    return s


def drift(doc: dict) -> tuple[list[int], list[int]]:
    """(done rows that still match at the last survey, rows that match nothing but are not done)."""
    still = [r["n"] for r in doc["rows"] if r["category"] in SURVEYED and status_of(doc, r["n"]) == "done" and doc["seen"].get(str(r["n"]), {}).get("hits", 0) > 0]
    gone = [r["n"] for r in doc["rows"] if r["category"] in SURVEYED and status_of(doc, r["n"]) != "done" and doc["seen"].get(str(r["n"]), {}).get("hits", 1) == 0]
    return still, gone


def verify(doc: dict) -> list[str]:
    """Problems with the data itself (pins, numbering, progress, accounting). Empty list: consistent."""
    bad: list[str] = []
    if doc.get("schema") != SCHEMA:
        return [f"adoption.json schema is {doc.get('schema')!r}, this plugin reads {SCHEMA}"]
    rows = doc.get("rows", [])
    for i, r in enumerate(rows, 1):
        if r.get("n") != i:
            bad.append(f"row at position {i} is numbered {r.get('n')}: rows are numbered by position and never renumbered")
            break
    if len(rows) != doc.get("nrows"):
        bad.append(f"{len(rows)} rows but {doc.get('nrows')} pinned: a row was added or removed outside `adoption survey`. Rows are append-only: "
                   "restore adoption.json, and add rows by surveying again")
    pins = doc.get("pins", {})
    for i, r in enumerate(rows, 1):
        want = pins.get(str(i))
        if want is None:
            bad.append(f"row {i} has no pin")
        elif want != pin_of(r):
            bad.append(f"row {i} is {pin_of(r)!r} but pinned as {want!r}: a row was inserted, moved or edited, which would move the statuses")
    for k, v in doc.get("progress", {}).items():
        if not k.isdigit() or not 1 <= int(k) <= len(rows):
            bad.append(f"progress names row {k}, which does not exist")
        elif v not in STATES[1:]:
            bad.append(f"progress of row {k} is {v!r}; the states are {', '.join(STATES)} (to do is the absence of an entry)")
    for r in rows:
        if r.get("category") not in CATEGORY_LABEL:
            bad.append(f"row {r.get('n')} has category {r.get('category')!r}")
    acc = doc.get("accounting") or {}
    if acc and acc.get("hits") != acc.get("in_rows", 0) + acc.get("kept", 0):
        bad.append(f"accounting: {acc.get('hits')} hits, {acc.get('in_rows')} in rows, {acc.get('kept')} kept: every hit must be a row or kept")
    return bad


# ---------------------------------------------------------------- rendering

def cell(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).replace("|", "\\|").strip()


def code(text: str, limit: int = 90) -> str:
    t = re.sub(r"\s+", " ", str(text)).strip()
    if len(t) > limit:
        t = t[:limit - 1] + "…"
    fence = "`" * (max((len(m) for m in re.findall(r"`+", t)), default=0) + 1)
    pad = " " if t.startswith("`") or t.endswith("`") else ""
    return cell(f"{fence}{pad}{t}{pad}{fence}")


def ranges(lines: list[int]) -> str:
    out, i = [], 0
    ls = sorted(set(lines))
    while i < len(ls):
        j = i
        while j + 1 < len(ls) and ls[j + 1] == ls[j] + 1:
            j += 1
        out.append(str(ls[i]) if i == j else f"{ls[i]}-{ls[j]}")
        i = j + 1
    return ", ".join(out)


def repo_label(doc: dict, rid: str) -> str:
    for r in doc["repos"]:
        if r["id"] == rid:
            return r["label"]
    return rid


TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "ADOPTION.md"
PLACEHOLDERS = ("name", "status", "repos", "about", "groups", "drift", "rows", "kept")


def frame() -> str:
    """templates/ADOPTION.md: the fixed text and the order of the sections. A missing frame or placeholder is an error, never a guess."""
    try:
        tpl = TEMPLATE.read_text(encoding="utf-8")
    except OSError as e:
        raise CliError(EXIT_USAGE, f"template missing: {TEMPLATE} ({e})") from e
    missing = [k for k in PLACEHOLDERS if "{{" + k + "}}" not in tpl]
    if missing:
        raise CliError(EXIT_USAGE, f"internal error: the template {TEMPLATE} lacks the placeholders {missing}")
    return tpl


def render(doc: dict, name: str) -> str:
    rows = doc["rows"]
    t = totals(doc)
    out: dict[str, str] = {"name": name, "status": f"Status: **{headline(doc)}**. {sentence(doc)}"}
    repos = doc["repos"]
    sv = doc.get("survey", {})
    out["repos"] = ("Repositories, read only from here (nothing in them is edited by brand-creator): "
                    + ", ".join(f"`{r['label']}`" + (f" ({sv.get('heads', {}).get(r['id'])})" if sv.get("heads", {}).get(r["id"]) else "") for r in repos) + ".")
    out["about"] = (f"{len(rows)} rows, surveyed on {sv.get('date', 'an unknown date')}. **Line numbers may drift: find the place by its content** (the Find "
                    "column), not by the line. Paths are relative to the repository. Each row has a status: to do, doing (made in the repository's working "
                    "tree, not committed) or done (committed; whether a row is done is the owner's call). Progress is stored apart from the rows "
                    "(`adoption status`); rows are never renumbered or removed, a new survey only adds rows at the end.")
    groups: dict[str, int] = {}
    for r in rows:
        groups[CATEGORY_LABEL[r["category"]]] = groups.get(CATEGORY_LABEL[r["category"]], 0) + 1
    out["groups"] = ("Groups: " + ", ".join(f"{g} {n}" for g, n in groups.items()) + ".") if groups else ""
    still, gone = drift(doc)
    out["drift"] = f"Check: row(s) {', '.join(map(str, still))} are marked done but still match at the last survey." if still else ""
    L: list[str] = []
    if rows:
        L += ["| # | Status | Group | Repo | File | Lines (may drift) | Find | Change |", "|---|---|---|---|---|---|---|---|"]
        for r in rows:
            sn = seen_of(doc, r)
            if r["category"] == "change":
                where = ranges(r.get("lines", [])) or "no line given"
            else:
                where = f"{sn['hits']} file(s)" if r["category"] == "path" else (ranges(sn["lines"]) or "no match now")
            L.append(f"| {r['n']} | {status_of(doc, r['n'])} | {cell(CATEGORY_LABEL[r['category']])} | {cell(repo_label(doc, r['repo']))} | "
                     f"{code(r['file'], 120)} | {cell(where)} | {code(r['find'])} | {cell(r['change'])} | {MARK}")
    else:
        L.append("No rows: the survey found nothing to change.")
    out["rows"] = "\n".join(L)
    K = [f"{t['kept_lines']} matching lines in {t['kept_files']} files that the survey saw and did not make rows, each with its reason. A row or "
         "this list accounts for every match.", ""]
    if doc["kept"]:
        by_reason: dict[str, list[dict]] = {}
        for k in doc["kept"]:
            by_reason.setdefault(k["reason"], []).append(k)
        for reason, ks in by_reason.items():
            K.append(f"- {reason}:")
            for k in ks:
                K.append(f"  - `{repo_label(doc, k['repo'])}` {code(k['file'], 120)} ({k['hits']} {'file' if k['category'] == 'path' else 'line'}"
                         f"{'' if k['hits'] == 1 else 's'}, {CATEGORY_LABEL[k['category']].lower()}) {MARK}")
    else:
        K.append("Nothing was kept out.")
    out["kept"] = "\n".join(K)
    # one pass over the frame: a value that happens to contain "{{...}}" (a file name, a Find excerpt) is never substituted again
    text = re.sub(r"\{\{(" + "|".join(PLACEHOLDERS) + r")\}\}", lambda m: out[m.group(1)], frame())
    return re.sub(r"\n{3,}", "\n\n", text).rstrip("\n") + "\n"
