#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator snapshot: sha256 lists of folders, for byte-identity and safety proofs.

  snapshot take <dir>... [--name N] [--out FILE] [--ignore GLOB] [--sha-list FILE]
        hash every file under each folder (read only; a folder may be outside the project, for example an adoption target
        you must leave untouched) and write the list as JSON. Default output: <data>/scratch/<slug>/snapshots/<name>.json.
  snapshot diff <before.json> <after.json> [--ignore GLOB]
        added, removed and changed files; exit 1 when anything differs, 0 when the two are byte-identical.
  snapshot verify <snapshot.json>
        compare the folders of a snapshot with what is on disk now (exit 1 on any difference).
A refactor of a generator is proven by `take`, the change, `take` again and `diff`: identical hashes or it is not a refactor.
`--out` and `--sha-list` must be inside the project or under the data directory. Relative paths are relative to the project.
"""
import fnmatch
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
from _common import (CliError, EXIT_FAIL, EXIT_USAGE, Parser, add_project_arg, confine, data_dir, fail, find_project, main_guard,  # noqa: E402
                     scratch_dir, sha256_file, try_find_project)

SKIP_DIRS = {".git", "__pycache__", "node_modules"}


def collect(folder: Path, ignore: list[str]) -> dict[str, str]:
    out = {}
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder).as_posix()
        if not p.is_file() or p.is_symlink() or any(part in SKIP_DIRS for part in p.relative_to(folder).parts):
            continue
        if any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(p.name, g) for g in ignore):
            continue
        out[rel] = sha256_file(p)
    return out


def flatten(doc: dict, ignore: list[str]) -> dict[str, str]:
    return {f"{d['label']}/{rel}": h for d in doc["dirs"] for rel, h in d["files"].items()
            if not any(fnmatch.fnmatch(f"{d['label']}/{rel}", g) or fnmatch.fnmatch(rel.rsplit('/', 1)[-1], g) for g in ignore)}


def load(path: str, project: Path | None) -> dict:
    p = Path(path).expanduser()
    if not p.is_absolute() and project is not None:
        p = project / p  # relative paths are relative to the project, like every other path of the command
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(EXIT_USAGE, f"cannot read snapshot {path}: {e}")
    if doc.get("schema") != 1 or "dirs" not in doc:
        fail(EXIT_USAGE, f"{path} is not a brand-creator snapshot")
    return doc


def out_path(project: Path | None, arg: str, what: str) -> Path:
    p = Path(arg).expanduser()
    if project is not None:
        try:
            return confine(project, p, what=what)
        except CliError:  # outside the project: allowed under the data dir, checked below
            pass
    real = Path(arg).expanduser().resolve()
    try:
        real.relative_to(data_dir())
    except ValueError:
        fail(EXIT_USAGE, f"{what} {arg} must be inside the project or under the data directory ({data_dir()})")
    return real


def show(label: str, items: list[str]) -> None:
    for i in items[:50]:
        print(f"  {label} {i}")
    if len(items) > 50:
        print(f"  ... and {len(items) - 50} more {label}")


def diff(a: dict[str, str], b: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    return (sorted(set(b) - set(a)), sorted(set(a) - set(b)), sorted(k for k in set(a) & set(b) if a[k] != b[k]))


def main() -> int:
    ap = Parser(prog="brand-creator snapshot", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=Parser)
    t = sub.add_parser("take", help="hash folders")
    t.add_argument("dirs", nargs="+")
    t.add_argument("--name", default="snapshot")
    t.add_argument("--out")
    t.add_argument("--ignore", action="append", default=[], metavar="GLOB")
    t.add_argument("--sha-list", help="also write a sha256sum-format list")
    d = sub.add_parser("diff", help="compare two snapshots")
    d.add_argument("before")
    d.add_argument("after")
    d.add_argument("--ignore", action="append", default=[], metavar="GLOB")
    v = sub.add_parser("verify", help="compare a snapshot with the folders now")
    v.add_argument("snapshot")
    v.add_argument("--ignore", action="append", default=[], metavar="GLOB")
    for sp in (t, d, v):  # --project also after the subcommand
        sp.add_argument("--project", default=__import__("argparse").SUPPRESS, help="brand project folder")
    a = ap.parse_args()
    project = try_find_project() if not getattr(a, "project", None) else find_project(a.project)
    if a.cmd == "take":
        dirs, labels = [], set()
        for raw in a.dirs:
            p = Path(raw).expanduser()
            p = (p if p.is_absolute() else (project or Path.cwd()) / p).resolve()
            if not p.is_dir():
                fail(EXIT_USAGE, f"not a folder: {raw}")
            label = p.name
            if label in labels:
                fail(EXIT_USAGE, f"two folders are both called {label}; snapshot them separately")
            labels.add(label)
            dirs.append((label, p))
        doc = {"schema": 1, "name": a.name, "dirs": [{"label": lab, "path": str(p), "files": collect(p, a.ignore)} for lab, p in dirs]}
        doc["count"] = sum(len(x["files"]) for x in doc["dirs"])
        if a.out:
            out = out_path(project, a.out, "--out")
        else:
            if project is None:
                fail(EXIT_USAGE, "no project to name the scratch folder after; pass --out under the data directory or --project")
            out = scratch_dir(project, "snapshots") / f"{a.name}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        if a.sha_list:
            sl = out_path(project, a.sha_list, "--sha-list")
            sl.write_text("".join(f"{h}  {k}\n" for k, h in sorted(flatten(doc, []).items())), encoding="utf-8")
        print(f"snapshot {a.name}: {doc['count']} file(s) in {len(dirs)} folder(s) -> {out}")
        return 0
    if a.cmd == "diff":
        added, removed, changed = diff(flatten(load(a.before, project), a.ignore), flatten(load(a.after, project), a.ignore))
    else:
        doc = load(a.snapshot, project)
        now = {"dirs": [{"label": x["label"], "files": collect(Path(x["path"]), a.ignore) if Path(x["path"]).is_dir() else {}} for x in doc["dirs"]]}
        added, removed, changed = diff(flatten(doc, a.ignore), flatten(now, a.ignore))
    if not (added or removed or changed):
        print("identical: no file added, removed or changed")
        return 0
    print(f"DIFFERENT: {len(added)} added, {len(removed)} removed, {len(changed)} changed")
    show("added", added), show("removed", removed), show("changed", changed)
    return EXIT_FAIL


main_guard(main)
