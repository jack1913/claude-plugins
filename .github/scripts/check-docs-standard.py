#!/usr/bin/env python3
"""Check the repo against docs/internals/docs-standard.md. Standard library only; run from the repository root.

Checks: skill frontmatter (§5: name, description length and person, SKILL.md length, reference index); agent
frontmatter (§5: supported fields only); plugin.json fields and the marketplace entry shape (§5); CHANGELOG.md
shape and version (§6); ADR status lines (§7); backticked paths in AGENTS.md tables that no longer exist; and each
plugin's commands page naming every skill.

Prints one line per finding: LEVEL<TAB>CODE<TAB>path[:line]<TAB>message. Without --strict every finding is a
warning and the exit code is 0; with --strict any finding exits 1. docs/archive/** is never checked.
"""
import argparse
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
findings = []


def report(code, path, msg, line=None):
    rel = path.relative_to(root) if path.is_absolute() else path
    findings.append((code, f"{rel}:{line}" if line else str(rel), msg))


def frontmatter(path):
    """Top-level keys of a YAML frontmatter block: plain, quoted, and folded/literal block scalars only.

    Returns (fields, body_lines), or (None, lines) when the file has no frontmatter."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None, lines
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None, lines
    fields, key, block = {}, None, None
    for ln in lines[1:end]:
        m = re.match(r"^([A-Za-z_][\w-]*):\s?(.*)$", ln)
        if m and not ln.startswith((" ", "\t")):
            key, val = m.group(1), m.group(2).strip()
            if val in (">", ">-", "|", "|-", ">+", "|+"):
                fields[key], block = "", key
            else:
                block = None
                if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
                    val = val[1:-1].replace("''", "'") if val[0] == "'" else val[1:-1]
                fields[key] = val
        elif block and ln.strip():
            fields[block] = (fields[block] + " " + ln.strip()).strip()
        elif key and not block and ln.startswith((" ", "\t")):
            fields[key] = (str(fields[key]) + " " + ln.strip()).strip()
    return fields, lines[end + 1 :]


# §5 skills
NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
SECOND_PERSON = re.compile(r"^(you\b|use this to\b)|\byou can\b", re.I)


def check_skill(skill_md):
    fm, body = frontmatter(skill_md)
    folder = skill_md.parent.name
    if fm is None:
        report("SKILL_NO_FRONTMATTER", skill_md, "no YAML frontmatter")
        return None
    name = fm.get("name", folder)
    if name != folder:
        report("SKILL_NAME_FOLDER", skill_md, f"name {name!r} differs from its folder {folder!r}")
    if not NAME_RE.match(name) or "anthropic" in name or "claude" in name:
        report("SKILL_NAME", skill_md, f"name {name!r}: lowercase letters, digits, hyphens, max 64, no anthropic/claude")
    desc, when = fm.get("description", ""), fm.get("when_to_use", "")
    typed_only = fm.get("disable-model-invocation", "").lower() == "true"
    if not desc:
        report("SKILL_NO_DESCRIPTION", skill_md, "description is missing")
    if len(desc) > 1024:
        report("SKILL_DESC_LENGTH", skill_md, f"description is {len(desc)} characters (max 1,024)")
    if len(desc) + len(when) > 1536:
        report("SKILL_LISTING_LENGTH", skill_md, f"description + when_to_use is {len(desc) + len(when)} (max 1,536)")
    elif not typed_only and len(desc) + len(when) > 1024:
        report("SKILL_LISTING_TARGET", skill_md, f"description + when_to_use is {len(desc) + len(when)} (target 1,024)")
    if SECOND_PERSON.search(desc):
        report("SKILL_DESC_PERSON", skill_md, "description addresses the reader; write it in the third person")
    if len(body) > 500:
        report("SKILL_BODY_LENGTH", skill_md, f"SKILL.md body is {len(body)} lines (max 500)")
    if "$ARGUMENTS" in "\n".join(body) and "argument-hint" not in fm:
        report("SKILL_ARGUMENT_HINT", skill_md, "uses $ARGUMENTS but has no argument-hint")
    refs = skill_md.parent / "references"
    if refs.is_dir() and len(list(refs.glob("*.md"))) > 5 and not (refs / "_index.md").is_file():
        report("SKILL_REFERENCE_INDEX", refs, "more than five reference files and no _index.md")
    return name


# §5 agents (https://code.claude.com/docs/en/plugins/components, "Frontmatter fields in plugin agents")
AGENT_FIELDS = {"name", "description", "model", "effort", "maxTurns", "autoCompactWindow", "tools",
                "disallowedTools", "skills", "memory", "background", "omitClaudeMd", "isolation", "color"}
AGENT_IGNORED = {"permissionMode", "hooks", "mcpServers", "initialPrompt"}


def check_agent(agent_md):
    fm, _ = frontmatter(agent_md)
    if fm is None:
        report("AGENT_NO_FRONTMATTER", agent_md, "no YAML frontmatter")
        return
    for k in fm:
        if k in AGENT_IGNORED:
            report("AGENT_IGNORED_FIELD", agent_md, f"{k} is ignored for plugin agents")
        elif k not in AGENT_FIELDS:
            report("AGENT_UNKNOWN_FIELD", agent_md, f"{k} is not a plugin agent field")
    if not fm.get("description"):
        report("AGENT_NO_DESCRIPTION", agent_md, "description is missing")


# §5 plugin.json and the marketplace entry
PLUGIN_FIELDS = ("name", "displayName", "description", "version", "author", "homepage", "repository", "license",
                 "keywords")
ENTRY_FIELDS = {"name", "source", "category", "tags"}


def check_plugin_json(plugin_dir):
    path = plugin_dir / ".claude-plugin" / "plugin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for f in PLUGIN_FIELDS:
        if not data.get(f):
            report("PLUGIN_FIELD", path, f"{f} is missing")
    if len(data.get("description", "")) > 120:
        report("PLUGIN_DESC_LENGTH", path, f"description is {len(data['description'])} characters (max 120)")
    want = f"https://github.com/jack1913/claude-plugins/tree/main/plugins/{plugin_dir.name}"
    if data.get("homepage") and data["homepage"] != want:
        report("PLUGIN_HOMEPAGE", path, f"homepage should be {want}")
    return data


def check_marketplace():
    path = root / ".claude-plugin" / "marketplace.json"
    for entry in json.loads(path.read_text(encoding="utf-8")).get("plugins", []):
        name = entry.get("name")
        extra = sorted(set(entry) - ENTRY_FIELDS)
        if extra:
            report("ENTRY_FIELDS", path, f"{name}: {', '.join(extra)} belong in plugin.json only")
        for f in ("category", "tags"):
            if f not in entry:
                report("ENTRY_FIELD", path, f"{name}: {f} is missing")


# §6 changelogs
VERSION_HEAD = re.compile(r"^## \[(\d+\.\d+\.\d+[^\]]*)\] - \d{4}-\d{2}-\d{2}( \[YANKED\])?$")


def check_changelog(plugin_dir, version):
    path = plugin_dir / "CHANGELOG.md"
    if not path.is_file():
        report("CHANGELOG_MISSING", path, "no CHANGELOG.md")
        return
    heads = [(i, ln) for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if ln.startswith("## ")]
    if not heads or heads[0][1] != "## [Unreleased]":
        report("CHANGELOG_UNRELEASED", path, "the first H2 must be '## [Unreleased]'")
    versions = []
    for i, ln in heads:
        if ln == "## [Unreleased]":
            continue
        m = VERSION_HEAD.match(ln)
        if m:
            versions.append(m.group(1))
        else:
            report("CHANGELOG_HEADING", path, f"{ln!r} is not '## [X.Y.Z] - YYYY-MM-DD'", i)
    if versions and versions[0] != version:
        report("CHANGELOG_VERSION", path, f"top version {versions[0]} differs from plugin.json {version}")


# §7 ADRs
ADR_STATUS = re.compile(r"^(proposed|accepted|deprecated|superseded by ADR-\d{4})$")


def check_adrs(adr_dir):
    for path in sorted(adr_dir.glob("ADR-*.md")):
        if path.name == "ADR-TEMPLATE.md":
            continue
        if not re.match(r"^ADR-\d{4}-[a-z0-9-]+\.md$", path.name):
            report("ADR_FILENAME", path, "name must be ADR-NNNN-kebab-title.md")
        for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = re.match(r"^- \*\*Status:\*\*\s*(.*)$", ln)
            if m:
                if not ADR_STATUS.match(m.group(1).strip()):
                    report("ADR_STATUS", path, f"status {m.group(1).strip()!r}: one of proposed, accepted, "
                           "deprecated, superseded by ADR-NNNN (what it replaces goes on a Supersedes line)", i)
                break
        else:
            report("ADR_STATUS", path, "no '- **Status:**' line")


# AGENTS.md pointer tables
PATH_TOKEN = re.compile(r"`([^`\s]+)`")


def check_agents_pointers(agents_md):
    """Backticked tokens with a '/' in table rows, resolved from the AGENTS.md folder or the repo root.

    A row holding a <placeholder> is skipped: its paths are relative to the placeholder. Bare file names
    are skipped too: they name a file in context, not a path."""
    base = agents_md.parent
    for i, ln in enumerate(agents_md.read_text(encoding="utf-8").splitlines(), 1):
        if not ln.startswith("|") or "<" in ln:
            continue
        for tok in PATH_TOKEN.findall(ln):
            tok = tok.split("#")[0].rstrip(":")
            if tok.startswith("@"):  # an @import, relative to the file that holds it
                continue
            if "/" not in tok or any(c in tok for c in "*{}$") or tok.startswith(("http", "-", "/")):
                continue
            if not ((base / tok).exists() or (root / tok).exists()):
                report("AGENTS_POINTER", agents_md, f"`{tok}` does not exist", i)


# commands page
def check_commands_page(plugin_dir, skills):
    page = plugin_dir / "docs" / "manual" / "reference" / "commands.md"
    if len(skills) < 2:
        return
    if not page.is_file():
        report("COMMANDS_PAGE", page, "missing (the plugin has more than one command)")
        return
    text = page.read_text(encoding="utf-8")
    for s in skills:
        if f"/{plugin_dir.name}:{s}" not in text:
            report("COMMANDS_PAGE_SKILL", page, f"/{plugin_dir.name}:{s} is not listed")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict", action="store_true", help="exit 1 on any finding")
    args = ap.parse_args()

    check_marketplace()
    for plugin_dir in sorted(p for p in (root / "plugins").iterdir() if p.is_dir()):
        data = check_plugin_json(plugin_dir)
        skills = [n for n in (check_skill(s) for s in sorted(plugin_dir.glob("skills/*/SKILL.md"))) if n]
        for a in sorted(plugin_dir.glob("agents/*.md")):
            check_agent(a)
        check_changelog(plugin_dir, data.get("version"))
        check_commands_page(plugin_dir, skills)
    for adr_dir in [root / "docs" / "adr", *sorted(root.glob("plugins/*/docs/adr"))]:
        if adr_dir.is_dir():
            check_adrs(adr_dir)
    for agents_md in [root / "AGENTS.md", *sorted(root.glob("plugins/*/AGENTS.md"))]:
        check_agents_pointers(agents_md)

    level = "ERROR" if args.strict else "WARN"
    for code, where, msg in findings:
        print(f"{level}\t{code}\t{where}\t{msg}")
    print(f"{len(findings)} findings", file=sys.stderr)
    sys.exit(1 if args.strict and findings else 0)


if __name__ == "__main__":
    main()
