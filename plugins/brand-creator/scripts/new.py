#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator new <slug>: scaffold a brand project from templates/.

Creates <root>/<slug>/BRAND-STATE.md, FACTS.md, DECISIONS.md and brief/BRIEF.md. Every other folder is created when its phase
starts (rounds/, research/, tokens/, assets/, history/ ...). Refuses to touch an existing project.
Root: --root, else the plugin's projects_root setting (CLAUDE_PLUGIN_OPTION_PROJECTS_ROOT), else the current folder.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from _common import (EXIT_FAIL, EXIT_USAGE, Parser, fail, main_guard, plugin_root, plugin_version, today)  # noqa: E402

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
TEMPLATES = {"BRAND-STATE.md": "BRAND-STATE.md", "FACTS.md": "FACTS.md", "BRIEF.md": "brief/BRIEF.md", "DECISIONS.md": "DECISIONS.md"}


def render(text: str, values: dict, name: str) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[^}]*\}\}", text)
    if left:
        fail(EXIT_FAIL, f"template {name} has unfilled placeholders: {sorted(set(left))}")
    return text


def main() -> int:
    ap = Parser(prog="brand-creator new", description=__doc__.split("\n\n")[0])
    ap.add_argument("slug", nargs="?", help="folder name, lowercase letters, digits, hyphens (default: brand-<yyyymmdd>)")
    ap.add_argument("--name", help="display name (default: slug in title case)")
    ap.add_argument("--tier", choices=("quick", "standard", "full"), default="quick",
                    help="scope tier; normally chosen at G0 and changed later with `state --set tier=...`")
    ap.add_argument("--root", help="folder that holds brand projects (default: projects_root setting, else the cwd)")
    a = ap.parse_args()
    slug = a.slug or "brand-" + today().replace("-", "")
    if not SLUG_RE.match(slug):
        fail(EXIT_USAGE, f"bad slug {slug!r}: use lowercase letters, digits and hyphens (max 63, no leading hyphen)")
    root = Path(a.root or os.environ.get("CLAUDE_PLUGIN_OPTION_PROJECTS_ROOT") or Path.cwd()).expanduser().resolve()
    if not root.is_dir():
        fail(EXIT_USAGE, f"projects folder {root} does not exist")
    proj = root / slug
    if proj.exists() and any(proj.iterdir()):
        fail(EXIT_FAIL, f"{proj} already exists and is not empty; refusing to overwrite. "
                        f"Resume it (brand-creator state --project {proj}) or pick another slug.")
    name = a.name or slug.replace("-", " ").title()
    values = {"slug": slug, "name": name, "name_q": json.dumps(name, ensure_ascii=False), "date": today(),
              "plugin_version": plugin_version(), "tier": a.tier}
    tpl_dir = plugin_root() / "templates"
    out = {}
    for tname, dest in TEMPLATES.items():
        src = tpl_dir / tname
        if not src.is_file():
            fail(EXIT_FAIL, f"template missing: {src}")
        out[dest] = render(src.read_text(encoding="utf-8"), values, tname)
    for dest, text in out.items():
        f = proj / dest
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    print(f"created brand project: {proj}")
    for dest in out:
        print(f"  {dest}")
    print(f"tier: {a.tier} (change with: brand-creator state --project {proj} --set tier=standard)")
    print(f"next: fill brief/BRIEF.md and FACTS.md, record G0 with: brand-creator state --project {proj} --record G0 \"<decision>\"")
    return 0


main_guard(main)
