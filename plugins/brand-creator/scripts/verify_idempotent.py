#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator verify-idempotent: run a build chain twice and require byte-identical output.

  verify-idempotent --cmd "{bc} emit web" --cmd "{bc} emit social --tagline X" [--root assets] [--allowlist FILE]

Each --cmd runs in order from the project folder (`{bc}` is this plugin's entry point with the same --data, `{project}`
the project path); the whole chain runs twice, the output trees under --root (default assets; folders whose name starts
with `_` are skipped) are hashed after each run and compared. The determinism rules (scripts/lib/determinism.py: PNG date
chunks, zip order and mtimes, PDF dates and IDs) are linted over the final tree.
A difference that cannot be removed goes in an explicit allowlist (qa/idempotence.json), one entry per file pattern:
  {"schema": 1, "entries": [{"path": "assets/social/*.png", "reason": "Chromium text rendering is byte-stable on one font stack only",
                             "substitute": {"check": "pixels-equal"}}]}
Every entry needs a reason AND a substitute check that the two versions must still pass:
  pixels-equal (same decoded RGBA), png-structure (same size and colour type), json-equal, zip-entries (same names and
  CRCs), text-equal-except {"pattern": regex} (equal once the regex is removed), assetutil (macOS: equal `assetutil --info`
  rendition lists, for an Assets.car), command {"command": "diff-tool {a} {b}"} (exit 0 = equivalent).
An allowlist entry that matches no difference is reported, so the list cannot rot.
"""
import fnmatch
import json
import os
import shlex
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
import determinism  # noqa: E402
from _common import (EXIT_USAGE, Parser, Report, add_project_arg, confine, fail, find_project, main_guard, rel, scratch_dir,  # noqa: E402
                     sha256_file)
from pxio import read_png  # noqa: E402

ALLOW_FILE = "qa/idempotence.json"
CHECKS = ("pixels-equal", "png-structure", "json-equal", "zip-entries", "text-equal-except", "assetutil", "command")


def load_allowlist(f: Path) -> list[dict]:
    if not f.is_file():
        return []
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        fail(EXIT_USAGE, f"{f.name} is not valid JSON: {e}")
    if doc.get("schema") != 1 or not isinstance(doc.get("entries"), list):
        fail(EXIT_USAGE, f"{f.name} needs {{\"schema\": 1, \"entries\": [...]}}")
    out = []
    for i, e in enumerate(doc["entries"]):
        ok = isinstance(e, dict) and isinstance(e.get("path"), str) and isinstance(e.get("reason"), str) and e["reason"].strip()
        sub = e.get("substitute") if isinstance(e, dict) else None
        if not ok or not isinstance(sub, dict) or sub.get("check") not in CHECKS:
            fail(EXIT_USAGE, f"{f.name}: entries[{i}] needs path, a non-empty reason and substitute.check (one of {', '.join(CHECKS)}): "
                             f"an allowed difference must be explained and replaced by a weaker check, never waved through")
        if sub["check"] == "command" and not isinstance(sub.get("command"), str):
            fail(EXIT_USAGE, f"{f.name}: entries[{i}]: substitute command needs a \"command\" with {{a}} and {{b}}")
        if sub["check"] == "text-equal-except" and not isinstance(sub.get("pattern"), str):
            fail(EXIT_USAGE, f"{f.name}: entries[{i}]: text-equal-except needs a \"pattern\"")
        out.append({"path": e["path"], "reason": e["reason"].strip(), "substitute": sub, "used": False})
    return out


def tree(project: Path, roots: list[Path]) -> dict[str, str]:
    out = {}
    for r in roots:
        if not r.is_dir():
            continue
        for p in sorted(r.rglob("*")):
            parts = p.relative_to(r).parts
            if p.is_file() and not p.is_symlink() and not any(x.startswith("_") or x.endswith(".tmp-bc") for x in parts):
                out[rel(project, p)] = sha256_file(p)
    return out


def png_px(p: Path):
    w, h, px = read_png(p.read_bytes())
    return w, h, bytes(px)


def assetutil(p: Path):
    return determinism.car_renditions(p)


def substitute(sub: dict, a: Path, b: Path) -> tuple[bool, str]:
    kind = sub["check"]
    try:
        if kind == "pixels-equal":
            return (png_px(a) == png_px(b)), "decoded RGBA pixels"
        if kind == "png-structure":
            (wa, ha, _), (wb, hb, _) = png_px(a), png_px(b)
            ca, cb = a.read_bytes()[25], b.read_bytes()[25]
            return (wa, ha, ca) == (wb, hb, cb), f"size {wa}x{ha}, colour type {ca}"
        if kind == "json-equal":
            return json.loads(a.read_text()) == json.loads(b.read_text()), "parsed JSON"
        if kind == "zip-entries":
            def entries(p):
                with zipfile.ZipFile(p) as z:
                    return sorted((i.filename, i.CRC, i.file_size) for i in z.infolist())
            return entries(a) == entries(b), "entry names, CRCs and sizes"
        if kind == "text-equal-except":
            import re
            rx = re.compile(sub["pattern"])
            return rx.sub("", a.read_text()) == rx.sub("", b.read_text()), f"text without /{sub['pattern']}/"
        if kind == "assetutil":
            return assetutil(a) == assetutil(b), "assetutil --info rendition list"
        if kind == "command":
            cmd = [x.replace("{a}", str(a)).replace("{b}", str(b)) for x in shlex.split(sub["command"])]
            return subprocess.run(cmd, capture_output=True).returncode == 0, f"`{sub['command']}`"
    except (ValueError, OSError, RuntimeError, zipfile.BadZipFile, KeyError) as e:
        return False, f"{kind} could not be evaluated: {e}"
    return False, kind


def run_chain(cmds: list[list[str]], project: Path, tag: str):
    for c in cmds:
        cp = subprocess.run(c, capture_output=True, text=True, cwd=project, env=os.environ.copy())
        if cp.returncode != 0:
            return f"{tag}: `{' '.join(c[:6])}` exited {cp.returncode}: {(cp.stderr.strip() or cp.stdout.strip())[-300:]}"
    return None


def main() -> int:
    ap = Parser(prog="brand-creator verify-idempotent", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--cmd", action="append", default=[], required=True, metavar="COMMAND", help="a command of the chain (repeatable, run in order); {bc} and {project} are substituted")
    ap.add_argument("--root", action="append", default=[], help="output folder inside the project to compare (repeatable; default assets)")
    ap.add_argument("--allowlist", help=f"allowlist file inside the project (default {ALLOW_FILE})")
    ap.add_argument("--no-lint", action="store_true", help="skip the determinism-rule lint of the final tree (printed in the report)")
    a = ap.parse_args()
    project = find_project(a.project)
    bc = [str(HERE.parent / "bin" / "brand-creator"), "--data", os.environ.get("BRAND_CREATOR_DATA", "")]
    cmds = []
    for raw in a.cmd:
        toks = []
        for t in shlex.split(raw):
            if t == "{bc}":
                toks += bc
            else:
                toks.append(t.replace("{project}", str(project)))
        if not toks:
            fail(EXIT_USAGE, "empty --cmd")
        cmds.append(toks)
    roots = [confine(project, r, what="--root") for r in (a.root or ["assets"])]
    allow_f = confine(project, a.allowlist or ALLOW_FILE, what="--allowlist")
    allow = load_allowlist(allow_f)
    rep = Report("idempotence", project, [allow_f], renderer="n/a")
    rep.extra = {"commands": a.cmd, "roots": [rel(project, r) for r in roots], "allowlist": rel(project, allow_f) if allow else None, "lint": not a.no_lint}
    work = scratch_dir(project, "idempotence")
    keep = work / "run1"
    if keep.exists():  # a previous verification's copies are scratch: move them aside, never delete
        shutil.move(str(keep), str(work / f"run1-{os.getpid()}-old"))
    err = run_chain(cmds, project, "run 1")
    if err:
        rep.add("idempotence:run1", "fail", "the chain runs", detail=err)
        return rep.finish()
    first = tree(project, roots)
    # copies of every file an allowlist entry could cover, so a substitute check can compare the two versions
    for relp in first:
        if any(fnmatch.fnmatch(relp, e["path"]) for e in allow):
            dst = keep / relp
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(project / relp, dst)
    err = run_chain(cmds, project, "run 2")
    if err:
        rep.add("idempotence:run2", "fail", "the chain runs again", detail=err)
        return rep.finish()
    second = tree(project, roots)
    changed = sorted(k for k in set(first) & set(second) if first[k] != second[k])
    appeared = sorted(set(second) - set(first))
    vanished = sorted(set(first) - set(second))
    for relp in appeared:
        rep.add(f"idempotence:{relp}", "fail", "second run is byte-identical", detail="the file appeared only in the second run (the first run did not write it)")
    for relp in vanished:
        rep.add(f"idempotence:{relp}", "fail", "second run is byte-identical", detail="the file existed after the first run and is gone after the second")
    for relp in changed:
        hit = next((e for e in allow if fnmatch.fnmatch(relp, e["path"])), None)
        if hit is None:
            rep.add(f"idempotence:{relp}", "fail", "second run is byte-identical",
                    detail="bytes differ between two runs: make the generator deterministic (see scripts/lib/determinism.py), or allowlist the file with a reason and a substitute check")
            continue
        hit["used"] = True
        ok, what = substitute(hit["substitute"], keep / relp, project / relp)
        rep.add(f"idempotence:{relp}", "pass" if ok else "fail", "allowlisted difference with a substitute check",
                detail=f"bytes differ; allowed: {hit['reason']}. Substitute check {hit['substitute']['check']} ({what}): {'passed' if ok else 'FAILED, the two versions are not equivalent'}",
                reason=hit["reason"], substitute=hit["substitute"])
    for e in allow:
        if not e["used"]:
            rep.add(f"allowlist:{e['path']}", "warn", "allowlist entry", detail=f"no file matching {e['path']} differed between the two runs: the entry is stale, remove it")
    if not (changed or appeared or vanished):
        rep.add("idempotence:trees", "pass", "second run is byte-identical", detail=f"{len(second)} file(s) under {', '.join(rel(project, r) for r in roots)} are identical after two runs")
    if not a.no_lint:
        bad = {relp: determinism.lint_file(project / relp) for relp in second}
        bad = {k: v for k, v in bad.items() if v}
        for relp, probs in sorted(bad.items()):
            rep.add(f"determinism:{relp}", "fail", "determinism rules", detail="; ".join(probs))
        if not bad:
            rep.add("determinism:rules", "pass", "determinism rules (PNG chunks, zip order and mtime, PDF dates)", detail=f"{len(second)} file(s) linted")
    else:
        rep.add("determinism:rules", "info", "determinism rules", detail="--no-lint: the rule lint was left out on purpose")
    return rep.finish()


main_guard(main)
