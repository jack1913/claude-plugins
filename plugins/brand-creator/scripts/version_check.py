#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator version --check: is the copy of the plugin this session runs the copy Claude Code has installed?

A session keeps the copy of a plugin it started with. After an update Claude Code records the new copy in installed_plugins.json, the file next to
the cache/ folder that holds the copies (<plugins>/cache/<marketplace>/<plugin>/<version>/), and only a new session runs it: a chain run in the old
session builds with the old tools. tools/finish.sh runs this first.

    python3 version_check.py <plugin root> [<folder the command runs in>]

Exit 0 when the running copy is the installed one; 1 when another copy of it is installed for this folder ("start a new session"); 0 with "not checked"
when it cannot tell: a copy that is not in a plugin cache (a checkout of the repository), or no readable record that applies to this folder.
Bootstrap script: standard library only, run on plain python3 (3.10 or newer, as setup and prereq), so it works before anything is set up.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def applies(entry: dict, here: Path) -> bool:
    """A user-scope install applies everywhere; a project or local one in its project folder and below."""
    if entry.get("scope") == "user":
        return True
    proj = entry.get("projectPath")
    if not isinstance(proj, str):
        return False
    try:
        p = Path(proj).resolve()
    except OSError:
        return False
    return here == p or p in here.parents


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve()
    here = Path(argv[2] if len(argv) > 2 else ".").resolve()
    version = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    said = f"brand-creator {version}"
    if len(root.parents) < 4 or root.parents[2].name != "cache":
        print(f"{said}: not checked: {root} is not a copy in a plugin cache (a checkout of the repository?), so there is no installed version to compare it with")
        return 0
    record = root.parents[3] / "installed_plugins.json"
    try:
        plugins = json.loads(record.read_text(encoding="utf-8"))["plugins"]
        entries = [e for v in plugins.values() for e in v if isinstance(e, dict) and isinstance(e.get("installPath"), str)]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print(f"{said}: not checked: {record} cannot be read ({type(e).__name__}: {e})")
        return 0
    mine = []   # the installs of this plugin (copies in the same cache folder) that apply here
    for e in entries:
        try:
            path = Path(e["installPath"]).resolve()
        except OSError:
            continue
        if path.parent == root.parent and applies(e, here):
            mine.append((path, e))
    if any(path == root for path, _ in mine):
        scope = next(e.get("scope", "?") for path, e in mine if path == root)
        print(f"{said}: the installed copy ({scope} scope)")
        return 0
    if not mine:
        print(f"{said}: not checked: {record} has no install of this plugin that applies to {here}")
        return 0
    other = "; ".join(f"{e.get('version', '?')} ({e.get('scope', '?')} scope, {path})" for path, e in mine)
    print(f"{said} is running here ({root}), and the installed copy is {other}: start a new session, so that the tools and the skills are the installed ones")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
