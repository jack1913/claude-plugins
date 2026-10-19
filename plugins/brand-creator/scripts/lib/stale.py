"""Staleness of a generated pack: tools/inputs.json (upstream sha256, plugin version, emitter code hashes, needles).

Shared by `brand-creator staleness` and `brand-creator check` (see scripts/staleness.py for the file format)."""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path

from _common import Report, plugin_root, plugin_version, rel, sha256_file

INPUTS_FILE = "tools/inputs.json"
# the files the packs are built from: tokens, logo art, the QA rules, the sentences the packs quote (FACTS.md), the deployment targets
# (INVENTORY.md) and the tray state declaration
DEFAULT_GLOBS = ["tokens/*.json", "assets/logo/*.svg", "assets/logo/*.png", "qa/*.json", "FACTS.md", "INVENTORY.md", "tray/*.json"]
EMITTER_GLOBS = ["scripts/emitters/*.py", "scripts/emitters/platform-specs.json", "scripts/emitters/print-regions.json", "scripts/lib/*.py"]


def expand(project: Path, globs: list[str]) -> list[Path]:
    out = set()
    for g in globs:
        for m in glob.glob(str(project / g), recursive=True):
            if Path(m).is_file():
                out.add(Path(m))
    return sorted(out)


def emitter_hashes() -> list[dict]:
    root = plugin_root()
    return [{"path": p.relative_to(root).as_posix(), "sha256": sha256_file(p)} for g in EMITTER_GLOBS for p in sorted(root.glob(g)) if p.is_file()]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def needle_present(base: Path, file: str, text: str) -> tuple[bool, str]:
    f = (base / file).resolve()
    if not f.is_file():
        return False, f"{file} not found"
    return norm(text) in norm(f.read_text(encoding="utf-8", errors="replace")), ""


def record(project: Path, globs: list[str], needles: list[dict]) -> dict:
    return {"schema": 1, "plugin_version": plugin_version(), "globs": globs,
            "inputs": [{"path": rel(project, p), "sha256": sha256_file(p)} for p in expand(project, globs)],
            "emitters": emitter_hashes(), "needles": needles}


def compare(project: Path, doc: dict, rep: Report) -> None:
    stale = 0
    if doc.get("plugin_version") != plugin_version():
        stale += 1
        rep.add("staleness:plugin-version", "fail", "pack matches the plugin version",
                detail=f"built with plugin {doc.get('plugin_version')}, running {plugin_version()}: rebuild the pack, then `staleness --write`")
    recorded = {i["path"]: i["sha256"] for i in doc.get("inputs", [])}
    now = {rel(project, p): sha256_file(p) for p in expand(project, doc.get("globs", DEFAULT_GLOBS))}
    for path, h in sorted(recorded.items()):
        if path not in now:
            stale += 1
            rep.add(f"staleness:input:{path}", "fail", "upstream input unchanged", detail=f"{path} is gone since the pack was built")
        elif now[path] != h:
            stale += 1
            rep.add(f"staleness:input:{path}", "fail", "upstream input unchanged", detail=f"{path} changed since the pack was built: rebuild, then `staleness --write`")
    for path in sorted(set(now) - set(recorded)):
        stale += 1
        rep.add(f"staleness:input:{path}", "fail", "upstream input unchanged", detail=f"{path} is new since the pack was built (it matches the input globs)")
    root = plugin_root()
    rec_em = {e["path"]: e["sha256"] for e in doc.get("emitters", [])}
    now_em = {e["path"]: e["sha256"] for e in emitter_hashes()}
    em_bad = sorted(p for p in set(rec_em) | set(now_em) if rec_em.get(p) != now_em.get(p))
    if em_bad:
        stale += 1
        rep.add("staleness:emitters", "fail", "emitter code unchanged since the pack was built",
                detail=f"{len(em_bad)} plugin file(s) differ: {', '.join(em_bad[:5])}{' ...' if len(em_bad) > 5 else ''}; rebuild the pack with the current emitters")
    for n in doc.get("needles", []):
        ok, why = needle_present(project, n["file"], n["text"])
        if not ok:
            stale += 1
            rep.add(f"staleness:needle:{n['file']}", "fail", "sentence still present in the sibling document",
                    detail=(why or f"the sentence {norm(n['text'])[:70]!r} is no longer in {n['file']}") + ": the document the pack quotes has moved on")
    if not stale:
        rep.add("staleness:current", "pass", "pack is current", detail=f"{len(recorded)} input(s), {len(rec_em)} emitter file(s), {len(doc.get('needles', []))} needle(s) all match "
                                                                     f"(built with plugin {doc.get('plugin_version')})")


def check_project(project: Path, rep: Report | None = None) -> Report:
    """Used by `brand-creator check`: the comparison as a Report (not written by this function)."""
    f = project / INPUTS_FILE
    rep = rep or Report("staleness", project, [f], renderer="n/a")
    doc = json.loads(f.read_text(encoding="utf-8"))
    compare(project, doc, rep)
    return rep
