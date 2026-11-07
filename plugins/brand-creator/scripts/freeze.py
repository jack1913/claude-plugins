#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator freeze <round> --name <name>: keep an approved round as written.

Copies what the round's boards show to history/<date>-<name>/: every board.html, index.html, preview.html and review.html in it,
the *.md at its top, every file those pages reach (read from the files and, in the plugin's Chromium, every file they request,
paths a script builds included), the scripts that built the round (*.py, *.mjs, *.js, *.sh) and its text records (*.json, *.md,
*.txt: motion proofs, frames.json, notes). The rest stays in rounds/ (FROZEN.md
says how much was left out, by folder). Before the copy becomes history it is loaded again in the browser: a file the round's pages
found that the copy cannot find stops the freeze, and nothing is written. A reference already broken in the round is listed in
FROZEN.md, not a failure.

    --whole   copy the whole round folder (what freeze did before 0.10.0)
    --static  read the references from the files only (no browser: a path a script builds is not seen); FROZEN.md says so

Without a set-up data directory (no browser) freeze stops and names --static and --whole: it never leaves the browser out silently.
Adds a "kept as written" banner (FROZEN.md, and an HTML comment at the top of every .html file), refuses to overwrite, and updates
history/MANIFEST.sha256 (sha256sum format, paths relative to history/). Requires gate G3 to be recorded
(`brand-creator state --record G3 "<decision>"`).
The guard hook allows this command and blocks every other way of adding files to history/.
"""
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import closure  # noqa: E402
from _common import (EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, CliError, Parser, add_project_arg, fail, find_project, history_files, main_guard,  # noqa: E402
                     read_history_manifest, require_gate, sha256_file, today, verify_history, write_history_manifest)

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def banner_text(rnd: str, date: str, name: str) -> str:
    return (f"KEPT AS WRITTEN: frozen from rounds/{rnd} on {date} as \"{name}\" by brand-creator freeze. "
            f"Do not edit. To change anything, make a new round.")


def plan_copy(src: Path, mode: str) -> tuple[list[Path], list[str]]:
    """(the files to copy, sorted; the references already broken in the round) for a mode: closure, static or whole."""
    if mode == "whole":
        return sorted(p for p in src.rglob("*") if p.is_file()), []
    starts = closure.starting_pages(src)
    if not any(p.name in closure.START_NAMES for p in starts):
        fail(EXIT_FAIL, f"{src.name} has no board.html, index.html, preview.html or review.html, so there is nothing that shows what to keep: "
                        "freeze --whole copies the whole round")
    kept, missing = closure.static_closure(src, starts)
    if mode == "closure":
        try:
            seen, seen_missing = closure.browser_closure(src, starts)
        except CliError as e:
            if e.code != EXIT_CANNOT:
                raise
            fail(EXIT_CANNOT, f"{e.message}. freeze reads what the boards show in the browser; without one, run freeze --static (the references "
                              "in the files only: a path a script builds is not seen) or freeze --whole (the whole round)")
        kept |= seen
        missing += [m for m in seen_missing if m not in missing]
    kept |= {p.resolve() for p in closure.builders(src) | closure.records(src)} | {p.resolve() for p in starts}
    return sorted(kept), missing


def left_out_text(src: Path, files: list[Path]) -> tuple[int, int, str]:
    """(count, bytes, "folder MB, ...") of the round's files not copied, by top folder, largest first."""
    keep = {p.resolve() for p in files}
    by: dict[str, int] = {}
    n = size = 0
    for p in src.rglob("*"):
        if p.is_file() and p.resolve() not in keep:
            s = p.stat().st_size
            n, size = n + 1, size + s
            top = p.relative_to(src).parts[0] if len(p.relative_to(src).parts) > 1 else "(top)"
            by[top] = by.get(top, 0) + s
    folders = ", ".join(f"{k} {v / 2**20:.1f} MB" for k, v in sorted(by.items(), key=lambda kv: (-kv[1], kv[0])))
    return n, size, folders


def main() -> int:
    ap = Parser(prog="brand-creator freeze", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("round", help="round folder name (r3) or number (3)")
    ap.add_argument("--name", required=True, help="short slug for the frozen folder, e.g. approved-board")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--whole", action="store_true", help="copy the whole round folder, not only what its boards show")
    ap.add_argument("--static", action="store_true", help="read what the boards show from the files only (no browser)")
    a = ap.parse_args()
    if a.whole and a.static:
        fail(EXIT_USAGE, "--whole and --static refuse each other: --whole copies everything, --static picks what the boards show without a browser")
    mode = "whole" if a.whole else "static" if a.static else "closure"
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
    files, broken = plan_copy(src, mode)
    n_left, size_left, folders = left_out_text(src, files)
    history.mkdir(exist_ok=True)
    tmp = history / f".tmp-freeze-{os.getpid()}"
    try:
        if mode == "whole":
            shutil.copytree(src, tmp, symlinks=False)
        else:
            for p in files:
                d = tmp / p.relative_to(src.resolve())
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, d)
        if mode == "closure":
            lost = closure.copy_losses(src, tmp)
            if lost:
                fail(EXIT_FAIL, f"the frozen copy of rounds/{rnd} would miss files its boards show ({'; '.join(lost[:5])}"
                                f"{f'; and {len(lost) - 5} more' if len(lost) > 5 else ''}): nothing was frozen. Run freeze --whole, and report this")
        text = banner_text(rnd, date, a.name)
        for f in sorted(tmp.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".html", ".htm"):
                f.write_bytes(f"<!-- {text} -->\n".encode() + f.read_bytes())
        notes = [f"mode: {mode}"]
        if mode != "whole":
            notes.append(f"left out: {n_left} files, {size_left / 2**20:.1f} MB" + (f" ({folders})" if folders else "") + "; they stay in rounds/ until a cleanup")
        notes += [f"already missing in the round: {m}" for m in broken]
        (tmp / "FROZEN.md").write_text(f"# Kept as written\n\n{text}\n\n" + "\n".join(f"- {x}" for x in notes) + "\n", encoding="utf-8")
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
    print(f"frozen rounds/{rnd} -> {dest.relative_to(project)} ({n} files, mode {mode}); history/MANIFEST.sha256 updated")
    if mode != "whole":
        print(f"left out {n_left} files, {size_left / 2**20:.1f} MB" + (f" ({folders})" if folders else "") + ": what no board of the round shows")
    for m in broken:
        print(f"already missing in the round (frozen as it is): {m}")
    return 0


main_guard(main)
