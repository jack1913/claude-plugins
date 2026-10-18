#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator specs-due: which platform-spec rows need a recheck?

Reads scripts/emitters/platform-specs.json, the one source of platform sizes, and lists the rows that are due:
  * stale: `checked` is older than stale_after_days (default 180) as of today (BRAND_CREATOR_TODAY overrides the date),
  * due soon: with --within N, rows that become stale within N days,
  * unverified or secondary: status U (unverified) and R (secondary source) rows are always listed, because their size
    has not been confirmed at the platform's own page; a row that is V (verified at the source) and fresh is not.
A maintainer tool: it needs no brand project. Run it before a release, and re-verify each listed row at its source_url
before changing `checked` (the date records a human reading, never a script run). --fail-on-due exits 1 when any row
is stale (the release check); --json prints the rows as data. --write-markdown FILE regenerates
skills/brand-creator/references/platform-specs.md from the JSON (never edited by hand; a test compares the two).
"""
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE / "emitters"))
import specs  # noqa: E402
from _common import EXIT_FAIL, Parser, main_guard, today  # noqa: E402


def due_rows(now: dt.date, within: int = 0) -> list[dict]:
    doc = specs.load()
    limit = int(doc["stale_after_days"])
    out = []
    for rid, row in doc["rows"].items():
        age = (now - dt.date.fromisoformat(row["checked"])).days
        left = limit - age
        reasons = []
        if left < 0:
            reasons.append(f"stale: checked {row['checked']}, {age} days ago (limit {limit})")
        elif left <= within:
            reasons.append(f"becomes stale in {left} day(s) (checked {row['checked']})")
        if row["status"] == "U":
            reasons.append("status U: unverified, never confirmed at the platform's page")
        elif row["status"] == "R":
            reasons.append("status R: read from a secondary source")
        if reasons:
            out.append({"id": rid, "surface": row["surface"], "status": row["status"], "checked": row["checked"], "age_days": age,
                        "days_left": left, "stale": left < 0, "reasons": reasons, "source_url": row["source_url"]})
    return sorted(out, key=lambda r: (not r["stale"], r["days_left"], r["id"]))


def main() -> int:
    ap = Parser(prog="brand-creator specs-due", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    ap.add_argument("--within", type=int, default=0, metavar="DAYS", help="also list rows that become stale within this many days")
    ap.add_argument("--json", action="store_true", help="print the rows as JSON")
    ap.add_argument("--fail-on-due", action="store_true", help="exit 1 when any row is stale")
    ap.add_argument("--markdown", action="store_true", help="print references/platform-specs.md (generated from the JSON) and exit")
    ap.add_argument("--write-markdown", metavar="FILE", help="write the generated platform-specs.md to FILE (a maintainer writes it into the plugin's references/)")
    a = ap.parse_args()
    if a.markdown:
        sys.stdout.write(specs.markdown())
        return 0
    if a.write_markdown:
        Path(a.write_markdown).write_text(specs.markdown(), encoding="utf-8")
        print(f"wrote {a.write_markdown}")
        return 0
    now = dt.date.fromisoformat(today())
    rows = due_rows(now, a.within)
    if a.json:
        print(json.dumps({"today": now.isoformat(), "rows": rows}, indent=2))
    else:
        total = len(specs.load()["rows"])
        print(f"platform-specs.json as of {now.isoformat()}: {len(rows)} of {total} row(s) due for a recheck")
        for r in rows:
            print(f"  {r['id']:<18} {r['status']}  {'STALE' if r['stale'] else 'due  '}  {r['surface']}")
            for why in r["reasons"]:
                print(f"      {why}")
            print(f"      recheck: {r['source_url']}")
    return EXIT_FAIL if a.fail_on_due and any(r["stale"] for r in rows) else 0


main_guard(main)
