#!/usr/bin/env python3
"""Check .claude-plugin/marketplace.json against the plugins/ folder. Standard library only; run from the repository root.

Fails when: the JSON does not parse; a plugin name is duplicated; a source is not "./plugins/<name>" or its folder is missing;
the folder has no .claude-plugin/plugin.json whose name equals the entry's name; or a folder under plugins/ is not listed.
"""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
market = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
errors = []
names = [p.get("name") for p in market.get("plugins", [])]
if len(names) != len(set(names)):
    errors.append("duplicate plugin names")
for p in market.get("plugins", []):
    name, src = p.get("name"), p.get("source")
    if src != f"./plugins/{name}":
        errors.append(f"{name}: source must be './plugins/{name}', got {src!r}")
        continue
    manifest = root / "plugins" / name / ".claude-plugin" / "plugin.json"
    if not manifest.is_file():
        errors.append(f"{name}: {manifest.relative_to(root)} is missing")
    elif json.loads(manifest.read_text(encoding="utf-8")).get("name") != name:
        errors.append(f"{name}: plugin.json name differs from the marketplace entry")
for d in sorted((root / "plugins").iterdir()):
    if d.is_dir() and d.name not in names:
        errors.append(f"plugins/{d.name} is not listed in the marketplace")
for e in errors:
    print("ERROR:", e, file=sys.stderr)
print(f"{len(names)} plugins checked, {len(errors)} errors")
sys.exit(1 if errors else 0)
