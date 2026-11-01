"""The brand kit around the applied skill (scripts/adaptlib/kitlib.py, scripts/kit.py) and the applied skill's kit mode.

Expected values are written out by hand from the Acme example (assets/logo/mark.svg is the large drawing, assets/logo/grid-mark.svg the small one;
tokens at assets/tokens/tokens.json), never read from the module under test."""
import shutil

import pytest
from helpers import FIXTURES, ROOT, bc

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_node]

TEMPLATE = ROOT / "templates" / "applied-skill" / "SKILL.md"


@pytest.fixture
def pack(acme):
    shutil.copy2(FIXTURES / "FACTS.md", acme / "FACTS.md")
    for kv in ("content_languages=en", "edition=1"):
        assert bc("state", "--set", kv, project=acme).returncode == 0
    assert bc("state", "--record", "G5", "approved (test)", project=acme).returncode == 0
    return acme


# ---------------------------------------------------------------- the applied skill builder: kit mode

def test_without_a_kit_the_applied_skill_keeps_its_paths_and_has_no_kit_section(pack):
    r = bc("applied-skill", "--yes", project=pack)
    assert r.returncode == 0, r.stderr
    text = (pack / ".claude" / "skills" / "acme-brand" / "SKILL.md").read_text(encoding="utf-8")
    assert "`../../../assets/tokens/tokens.json`" in text
    assert "- `../../../assets/logo/mark.svg`" in text
    assert "uses `assets/logo/grid-mark.svg`" in text                      # a band line keeps the drawing's project path
    assert "## The kit" not in text and "{{" not in text
    assert "rule.\n\n## Colour" in text                                    # the dropped {{kit}} line leaves one blank line, not two


def test_in_kit_mode_every_path_points_inside_the_kit(pack):
    import adapt
    section = "## The kit\n\nx"
    text = adapt.applied_skill_md(pack, TEMPLATE.read_text(encoding="utf-8"), kit={"prefix": "brand/", "section": section})
    assert "../../../" not in text
    assert "- `brand/assets/logo/mark.svg`" in text
    assert "`brand/assets/tokens/tokens.json`" in text
    assert "uses `brand/assets/logo/grid-mark.svg`" in text and "uses `brand/assets/logo/mark.svg`" in text    # the band lines too
    assert "{{" not in text
    assert 0 < text.index("## The kit") < text.index("## Colour")
    assert "rule.\n\n## The kit\n\nx\n\n## Colour" in text                 # between the "Use this whenever" paragraph and the colour section


def test_kit_mode_changes_only_the_paths_and_the_kit_section(pack):
    """The same builder writes both: with the kit's paths put back and the section taken out, the text is the one without a kit."""
    import adapt
    template = TEMPLATE.read_text(encoding="utf-8")
    plain = adapt.applied_skill_md(pack, template)
    in_kit = adapt.applied_skill_md(pack, template, kit={"prefix": "brand/", "section": "## The kit\n\nx"})
    back = in_kit.replace("## The kit\n\nx\n\n", "").replace("`brand/assets/tokens/", "`../../../assets/tokens/").replace("- `brand/", "- `../../../")
    back = back.replace("uses `brand/", "uses `")
    assert back == plain


def test_a_kit_mode_template_that_has_no_kit_line_still_gets_the_kit_paths(pack):
    """A template with no {{kit}} writes no kit section (as every placeholder a template leaves out writes nothing), and the paths still point into the kit."""
    import adapt
    template = TEMPLATE.read_text(encoding="utf-8").replace("{{kit}}\n\n", "")
    text = adapt.applied_skill_md(pack, template, kit={"prefix": "brand/", "section": "## The kit\n\nx"})
    assert "## The kit" not in text and "`brand/assets/tokens/tokens.json`" in text and "../../../" not in text


def test_kit_mode_writes_braces_in_the_kit_section_as_they_are(pack):
    import adapt
    section = "## The kit\n\nsee {{facts}} and {{tokens}} and {{kit}}"
    text = adapt.applied_skill_md(pack, TEMPLATE.read_text(encoding="utf-8"), kit={"prefix": "brand/", "section": section})
    assert "see {{facts}} and {{tokens}} and {{kit}}" in text
