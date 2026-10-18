#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator freeze <round> --name <name>: keep an approved round as written.

Copies rounds/<round>/ to history/<date>-<name>/, adds a "kept as written" banner (FROZEN.md, and an HTML comment at
the top of every .html file), refuses to overwrite, and updates history/MANIFEST.sha256 (sha256sum format, paths
relative to history/). Requires gate G3 to be recorded (`brand-creator state --record G3 "<decision>"`).
The guard hook allows this command and blocks every other way of adding files to history/.
"""
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from _common import (EXIT_FAIL, EXIT_USAGE, Parser, add_project_arg, fail, find_project, history_files, main_guard,  # noqa: E402
                     read_history_manifest, require_gate, sha256_file, today, verify_history, write_history_manifest)

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def banner_text(rnd: str, date: str, name: str) -> str:
    return (f"KEPT AS WRITTEN: frozen from rounds/{rnd} on {date} as \"{name}\" by brand-creator freeze. "
            f"Do not edit. To change anything, make a new round.")


def main() -> int:
    ap = Parser(prog="brand-creator freeze", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("round", help="round folder name (r3) or number (3)")
    ap.add_argument("--name", required=True, help="short slug for the frozen folder, e.g. approved-board")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today)")
    a = ap.parse_args()
    project = find_project(a.project)
    rnd = a.round if a.round.startswith("r") else f"r{a.round}"
    if not re.fullmatch(r"r\d+", rnd):
        fail(EXIT_USAGE, f"bad round {a.round!r}: use r3 or 3")
    if not NAME_RE.match(a.name):
        fail(EXIT_USAGE, f"bad --name {a.name!r}: lowercase letters, digits, hyphens")
    date = a.date or today()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        fail(EXIT_USAGE, f"bad --date {date!r}: YYYY-MM-DD")
    require_gate(project, "G3", for_what="freeze")
    src = project / "rounds" / rnd
    if not src.is_dir():
        fail(EXIT_FAIL, f"rounds/{rnd} does not exist in {project}")
    links = [p for p in src.rglob("*") if p.is_symlink()]
    if links:
        fail(EXIT_FAIL, f"rounds/{rnd} contains symlinks ({links[0].relative_to(project)}); a frozen copy must be self-contained")
    history = project / "history"
    problems = verify_history(project)
    if problems:
        fail(EXIT_FAIL, "history/ is not intact, refusing to add to it: " + "; ".join(problems[:5]) +
                        ". Run `brand-creator check` and resolve it first.")
    dest = history / f"{date}-{a.name}"
    if dest.exists():
        fail(EXIT_FAIL, f"{dest.relative_to(project)} already exists; freeze never overwrites. Pick another --name.")
    history.mkdir(exist_ok=True)
    tmp = history / f".tmp-freeze-{os.getpid()}"
    try:
        shutil.copytree(src, tmp, symlinks=False)
        text = banner_text(rnd, date, a.name)
        for f in sorted(tmp.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".html", ".htm"):
                f.write_bytes(f"<!-- {text} -->\n".encode() + f.read_bytes())
        (tmp / "FROZEN.md").write_text(f"# Kept as written\n\n{text}\n", encoding="utf-8")
        os.rename(tmp, dest)
    except BaseException:
        if tmp.exists():
            shutil.move(str(tmp), str(history / f".failed-freeze-{os.getpid()}"))
        raise
    entries = read_history_manifest(history)
    for f in history_files(dest):
        entries[f.relative_to(history).as_posix()] = sha256_file(f)
    write_history_manifest(history, entries)
    n = sum(1 for _ in history_files(dest))
    print(f"frozen rounds/{rnd} -> {dest.relative_to(project)} ({n} files); history/MANIFEST.sha256 updated")
    return 0


main_guard(main)
