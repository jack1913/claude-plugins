"""Structure checks for the marketplace and the batbelt plugin."""

import json
import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
BATBELT = ROOT / "plugins" / "batbelt"
SKILLS = BATBELT / "skills"
EXPECTED_SKILLS = {"grill-me", "prove-it", "onboard-repo", "puppet-master"}


def _frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, f"{path}: no YAML frontmatter"
    return yaml.safe_load(m.group(1))


def _skill_files():
    # Every SKILL.md, including onboard-repo's templates (stamped into other repos).
    return sorted(SKILLS.rglob("SKILL.md"))


def test_the_four_skills_are_present():
    assert {p.name for p in SKILLS.iterdir() if p.is_dir()} == EXPECTED_SKILLS
    for name in EXPECTED_SKILLS:
        assert (SKILLS / name / "SKILL.md").is_file()


def test_only_onboard_repo_is_typed_only():
    # grill-me starts when the user says "grill me"; onboard-repo writes into a repository, so it
    # runs only when typed.
    typed_only = {
        name for name in EXPECTED_SKILLS if _frontmatter(SKILLS / name / "SKILL.md").get("disable-model-invocation")
    }
    assert typed_only == {"onboard-repo"}


def test_grilling_was_merged_into_grill_me():
    assert not (SKILLS / "grilling").exists()
    body = (SKILLS / "grill-me" / "SKILL.md").read_text(encoding="utf-8")
    assert "one question at a time" in body.lower()
    assert "recommended answer" in body
    assert "grilling" not in body


@pytest.mark.parametrize("path", _skill_files(), ids=lambda p: str(p.relative_to(SKILLS)))
def test_skill_frontmatter_parses_as_yaml(path):
    fm = _frontmatter(path)
    assert isinstance(fm, dict)
    assert isinstance(fm.get("description"), str) and fm["description"].strip()
    if path.parent.parent == SKILLS:
        assert fm.get("name") == path.parent.name


def test_plugin_manifest():
    pj = json.loads((BATBELT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert pj["name"] == "batbelt"
    assert re.fullmatch(r"\d+\.\d+\.\d+", pj["version"])


def test_marketplace_lists_only_plugins_whose_source_exists():
    mp = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    names = [p["name"] for p in mp["plugins"]]
    assert len(names) == len(set(names)), "duplicate plugin names"
    assert "batbelt" in names
    for p in mp["plugins"]:
        src = p["source"]
        if isinstance(src, str):  # a folder in this repository
            assert src.startswith("./"), f"{p['name']}: relative source must start with ./"
            target = (ROOT / src).resolve()
            assert target.is_dir(), f"{p['name']}: {src} does not exist"
            assert (target / ".claude-plugin" / "plugin.json").is_file(), f"{p['name']}: no plugin.json"
            pj = json.loads((target / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            assert pj["name"] == p["name"]


def test_no_installer_artefacts_or_bytecode():
    bad = [
        str(p.relative_to(ROOT))
        for p in BATBELT.rglob("*")
        if p.name == ".claude-configs-owned" or p.name == "__pycache__" or p.suffix == ".pyc"
    ]
    assert not bad, bad


def test_no_symlinks_in_the_plugin():
    assert not [p for p in BATBELT.rglob("*") if p.is_symlink()]


def test_skills_do_not_assume_a_user_level_install():
    # The plugin cache is not ~/.claude/skills/<name>/; paths must come from
    # ${CLAUDE_SKILL_DIR}. Mentions that warn against the assumption are allowed.
    skill = (SKILLS / "onboard-repo" / "SKILL.md").read_text(encoding="utf-8")
    assert "${CLAUDE_SKILL_DIR}" in skill
    for p in SKILLS.rglob("*.md"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if re.search(r"~/\.claude/skills/(onboard-repo|prove-it|grill)", line):
                assert "Never assume" in line or "assume" in line, f"{p}: {line}"


def test_commands_users_type_carry_the_plugin_namespace():
    bare = re.compile(r"(?<![\w:/.-])/(onboard-repo|grill-me|prove-it)\b")
    hits = [
        f"{p.relative_to(ROOT)}:{i}"
        for p in SKILLS.rglob("*.md")
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if bare.search(line)
    ]
    assert not hits, hits


_MD_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)")


def test_no_markdown_link_escapes_the_plugin():
    # A link leaving the plugin directory breaks once the plugin is copied to the cache.
    root = BATBELT.resolve()
    offenders = []
    for p in SKILLS.rglob("*.md"):
        for target in _MD_LINK.findall(p.read_text(encoding="utf-8")):
            if target.startswith("#") or "://" in target or target.startswith("mailto:"):
                continue
            if target.startswith("/"):
                offenders.append(f"{p.relative_to(ROOT)} -> {target}")
                continue
            landing = (p.parent / target.split("#", 1)[0]).resolve()
            if root != landing and root not in landing.parents:
                offenders.append(f"{p.relative_to(ROOT)} -> {target}")
    assert not offenders, offenders
