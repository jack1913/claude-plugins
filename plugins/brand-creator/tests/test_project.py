"""new, state, freeze, project discovery and path confinement."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from helpers import ROOT, bc, make_project, mutate

import _common


def test_new_scaffolds_a_project(tmp_path):
    p = make_project(tmp_path, "acme", tier="standard", name='Acme "Quoted" Co')
    assert (p / "BRAND-STATE.md").is_file() and (p / "FACTS.md").is_file() and (p / "brief" / "BRIEF.md").is_file()
    assert (p / "DECISIONS.md").is_file() and "{{" not in (p / "DECISIONS.md").read_text()
    st = _common.State(p / "BRAND-STATE.md").data()
    assert st["slug"] == "acme" and st["tier"] == "standard" and st["name"] == 'Acme "Quoted" Co'
    assert st["phase"] == "P0" and st["architecture"] == "standalone"
    assert list(st["gates"]) == ["G0", "G1", "G1s", "G2", "G2b", "G3", "G4", "G4w", "G4p", "G5", "G6", "G7"]
    assert all(v == "" for v in st["gates"].values())
    text = (p / "BRAND-STATE.md").read_text()
    assert "{{" not in text and "## Collaboration" in text and "## Directions" in text
    assert "## Forbidden" in (p / "brief" / "BRIEF.md").read_text()
    assert not (p / "rounds").exists() and not (p / "history").exists()  # folders appear when their phase starts


def test_new_refuses_to_overwrite_and_validates_the_slug(tmp_path):
    make_project(tmp_path, "acme")
    r = bc("new", "acme", "--root", str(tmp_path), data=tmp_path / "d")
    assert r.returncode == 1 and "refusing to overwrite" in r.stderr
    r = bc("new", "Bad Slug", "--root", str(tmp_path), data=tmp_path / "d")
    assert r.returncode == 2


def test_new_default_slug_is_dated(tmp_path):
    r = bc("new", "--root", str(tmp_path), data=tmp_path / "d")
    assert r.returncode == 0 and (tmp_path / "brand-20261017" / "BRAND-STATE.md").is_file()


def test_new_reads_projects_root_from_the_plugin_setting(tmp_path):
    root = tmp_path / "brands"
    root.mkdir()
    r = bc("new", "viaconfig", env={"CLAUDE_PLUGIN_OPTION_PROJECTS_ROOT": str(root)}, cwd=tmp_path, data=tmp_path / "d")
    assert r.returncode == 0 and (root / "viaconfig" / "BRAND-STATE.md").is_file()


_NO_GIT_SETTINGS = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}   # the answer must come from the project's own file


def _git_ignores(repo: Path, rel: str) -> bool:
    """Whether git ignores the path in `repo` (exit 0: ignored, 1: not ignored; anything else is an error, not an answer)."""
    r = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", rel], capture_output=True, text=True, env=_NO_GIT_SETTINGS)
    assert r.returncode in (0, 1), r.stderr
    return r.returncode == 0


def test_new_writes_a_gitignore_that_keeps_the_full_page_site_captures_out_of_git(tmp_path):
    """G4-13 (O8): the whole-page still of every captured site is large and is not a file the owner works from; the boards use the smaller
    stills and the thumbnails, so a new project ignores `research/site-refs/*/1440-full.png` and nothing else."""
    r = bc("new", "acme", "--root", str(tmp_path), data=tmp_path / "d")
    assert r.returncode == 0, r.stderr
    assert "\n  .gitignore\n" in r.stdout                      # the run lists it with the other files it wrote
    p = tmp_path / "acme"
    text = (p / ".gitignore").read_text(encoding="utf-8")
    assert "{{" not in text and "research/site-refs/*/1440-full.png" in text.splitlines()
    # what git itself does with it, not only what the file says
    assert subprocess.run(["git", "-C", str(p), "init", "-q"], capture_output=True, env=_NO_GIT_SETTINGS).returncode == 0
    site = p / "research" / "site-refs" / "example-com"
    site.mkdir(parents=True)
    for name in ("1440.png", "390.png", "1440-full.png", "thumb-1440.jpg", "thumb-390.jpg", "capture.json"):
        (site / name).write_bytes(b"x")
    assert _git_ignores(p, "research/site-refs/example-com/1440-full.png")
    for name in ("1440.png", "390.png", "thumb-1440.jpg", "thumb-390.jpg", "capture.json"):
        assert not _git_ignores(p, f"research/site-refs/example-com/{name}"), name
    assert not _git_ignores(p, "BRAND-STATE.md")


def test_new_leaves_an_existing_gitignore_as_it_is(tmp_path):
    """G4-13: an existing `.gitignore` is never overwritten. `new` refuses a folder that holds anything (this file included), so the file
    keeps its bytes and nothing is written beside it."""
    folder = tmp_path / "acme"
    folder.mkdir()
    mine = b"# the owner's own\r\n*.tmp\r\n"
    (folder / ".gitignore").write_bytes(mine)
    r = bc("new", "acme", "--root", str(tmp_path), data=tmp_path / "d")
    assert r.returncode == 1 and "refusing to overwrite" in r.stderr
    assert (folder / ".gitignore").read_bytes() == mine and [e.name for e in folder.iterdir()] == [".gitignore"]


def test_the_manual_says_how_to_add_the_ignore_line_to_an_older_project():
    """G4-13: a project made before this release has no `.gitignore` from `new`; the site references page says what to add by hand."""
    page = (ROOT / "docs" / "manual" / "use" / "get-reference-pages-for-your-site.md").read_text(encoding="utf-8")
    assert "`.gitignore`" in page and "research/site-refs/*/1440-full.png" in page


def test_no_data_dir_is_a_clear_usage_error(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "BRAND_CREATOR_DATA"}
    import subprocess
    r = subprocess.run([str(ROOT / "bin" / "brand-creator"), "state"], capture_output=True, text=True, env=env, cwd=tmp_path)
    assert r.returncode == 2 and "--data" in r.stderr and "BRAND_CREATOR_DATA" in r.stderr


def test_project_discovery_walks_up_and_errors_clearly(tmp_path):
    p = make_project(tmp_path)
    deep = p / "a" / "b"
    deep.mkdir(parents=True)
    r = bc("state", "--json", cwd=deep, data=tmp_path / "d")
    assert r.returncode == 0 and json.loads(r.stdout)["state"]["slug"] == "acme"
    empty = tmp_path / "elsewhere"
    empty.mkdir()
    r = bc("state", cwd=empty, data=tmp_path / "d")
    assert r.returncode == 2 and "no brand project found; pass --project" in r.stderr
    r = bc("state", "--project-auto", cwd=empty, data=tmp_path / "d")
    assert r.returncode == 0 and "no brand project found" in r.stdout


def test_raising_the_tier_names_the_chapters_and_facts_the_new_tier_needs(tmp_path):
    p = make_project(tmp_path, tier="standard")
    r = bc("state", "--set", "tier=full", project=p)
    assert r.returncode == 0, r.stderr
    assert "tier raised: standard -> full" in r.stdout
    assert "adoption, launch" in r.stdout and "INVENTORY.md" in r.stdout and "Open: <what it waits for>" in r.stdout and "book:open-items" in r.stdout
    for cid in ("adoption", "launch"):   # what the lint needs is named from the same registry: standard's own chapters are missing too, so they are listed first
        assert cid in r.stdout.split("INVENTORY.md")[0]
    same = bc("state", "--set", "tier=full", project=p)
    assert same.returncode == 0 and "tier raised" not in same.stdout and same.stdout.strip() == ""
    low = bc("state", "--set", "tier=standard", project=p)
    assert low.returncode == 0 and low.stdout.strip() == ""
    # what the project already has is not listed again
    (p / "book" / "chapters").mkdir(parents=True)
    for cid in ("adoption", "launch"):
        (p / "book" / "chapters" / f"{cid}.md").write_text("## x\n")
    (p / "INVENTORY.md").write_text("# Inventory\n")
    r = bc("state", "--set", "tier=full", project=p)
    assert "adoption" not in r.stdout and "launch" not in r.stdout and "INVENTORY.md" not in r.stdout
    q = make_project(tmp_path, slug="two", tier="quick")
    r = bc("state", "--set", "tier=standard", project=q)
    assert "tier raised: quick -> standard" in r.stdout and "adoption" not in r.stdout and "INVENTORY.md" not in r.stdout
    q1 = make_project(tmp_path, slug="five", tier="standard")
    j = bc("state", "--set", "tier=full", "--json", project=q1)   # the lines go to stderr, so stdout still parses
    assert j.returncode == 0 and isinstance(json.loads(j.stdout), dict) and "tier raised: standard -> full" in j.stderr
    q2 = make_project(tmp_path, slug="four", tier="standard")
    g = bc("state", "--set", "tier=full", "--get", "tier", project=q2)
    assert g.stdout.strip() == "full" and "tier raised: standard -> full" in g.stderr
    r = bc("state", "--set", "inventory=none (no target repo)", project=make_project(tmp_path, slug="three", tier="standard"))
    assert r.stdout.strip() == ""


def test_raising_the_tier_after_g4_names_the_motion_decision_and_reads_a_missing_tier_as_quick(tmp_path):
    p = make_project(tmp_path, tier="quick")
    assert bc("state", "--record", "G4", "approved", project=p).returncode == 0
    r = bc("state", "--set", "tier=standard", project=p)
    assert r.returncode == 0 and "motion decision" in r.stdout and "motion:decided" in r.stdout and "brand-creator motion --off" in r.stdout, (r.stdout, r.stderr)
    (p / "motion").mkdir()
    (p / "motion" / "motion.json").write_text('{"schema": 1, "motion": "off", "reason": "nothing moves"}\n')
    r = bc("state", "--set", "tier=full", project=p)
    assert "motion decision" not in r.stdout, r.stdout
    r0 = make_project(tmp_path, slug="beforeg4", tier="quick")           # G4 not recorded: no motion line
    r = bc("state", "--set", "tier=standard", project=r0)
    assert r.returncode == 0 and "motion decision" not in r.stdout, (r.stdout, r.stderr)
    q = make_project(tmp_path, slug="notier", tier="quick")
    st = q / "BRAND-STATE.md"
    st.write_text("".join(ln for ln in st.read_text().splitlines(True) if not ln.startswith("tier:")))
    r = bc("state", "--set", "tier=standard", project=q)
    assert r.returncode == 0 and "tier raised: quick -> standard" in r.stdout, (r.stdout, r.stderr)


def test_raising_the_tier_reads_the_chapter_file_of_each_content_language(tmp_path):
    p = make_project(tmp_path, tier="standard")
    assert bc("state", "--set", "content_languages=pl,en", project=p).returncode == 0
    (p / "book" / "chapters").mkdir(parents=True)
    for name in ("adoption.pl.md", "adoption.en.md", "launch.pl.md"):
        (p / "book" / "chapters" / name).write_text("## x\n")
    r = bc("state", "--set", "tier=full", project=p)
    head = r.stdout.split("INVENTORY.md")[0]
    assert "launch" in head and "adoption" not in head, r.stdout
    (p / "book" / "chapters" / "launch.en.md").write_text("## x\n")
    r = bc("state", "--set", "tier=standard", project=p)
    r = bc("state", "--set", "tier=full", project=p)
    assert "launch" not in r.stdout.split("INVENTORY.md")[0], r.stdout


def test_state_record_require_get_set_bump(tmp_path):
    p = make_project(tmp_path)
    d = tmp_path / "d"
    r = bc("state", "--require", "G3", project=p, data=d)
    assert r.returncode == 1 and "G3" in r.stderr and "--record" in r.stderr
    assert bc("state", "--record", "G3", "approved board r2", project=p, data=d).returncode == 0
    r = bc("state", "--require", "G3", project=p, data=d)
    assert r.returncode == 0 and "2026-10-17 approved board r2" in r.stdout
    assert bc("state", "--get", "gates.G3", project=p, data=d).stdout.strip() == "2026-10-17 approved board r2"
    assert bc("state", "--set", "tier=full", "--set", "phase=P3", project=p, data=d).returncode == 0
    assert bc("state", "--get", "tier", project=p, data=d).stdout.strip() == "full"
    for expect in ("1", "2"):
        assert bc("state", "--bump", "fixes_per_area.logo", project=p, data=d).stdout.strip().endswith(f"= {expect}")
    assert bc("state", "--get", "fixes_per_area.logo", project=p, data=d).stdout.strip() == "2"
    # comments in the frontmatter survive edits
    assert "# quick | standard | full" in (p / "BRAND-STATE.md").read_text()
    r = bc("state", "--set", "gates.G1=x", project=p, data=d)
    assert r.returncode == 2 and "--record" in r.stderr
    assert bc("state", "--require", "G9", project=p, data=d).returncode == 2
    assert bc("state", "--get", "nope", project=p, data=d).returncode == 1


def test_state_summary_lists_directions(tmp_path):
    p = make_project(tmp_path)
    mutate(p / "BRAND-STATE.md", "|---|---|---|---|---|---|---|\n", "|---|---|---|---|---|---|---|\n| Compass | A | calm | liked | | | |\n")
    j = json.loads(bc("state", "--json", project=p, data=tmp_path / "d").stdout)
    assert j["directions"][0]["name"] == "Compass" and j["directions"][0]["letter"] == "A"
    assert "Compass (A)" in bc("state", project=p, data=tmp_path / "d").stdout


def test_state_counts_round_0_as_a_real_latest_round(tmp_path):
    """Round 0 is the style board. A truthiness test on the round number made a project whose only round is r0 report no latest round."""
    p, d = make_project(tmp_path), tmp_path / "d"
    j = json.loads(bc("state", "--json", project=p, data=d).stdout)
    assert j["rounds"] == [] and j["latest_round"] is None
    assert "rounds: -   latest: -" in bc("state", project=p, data=d).stdout
    (p / "rounds" / "r0").mkdir(parents=True)
    j = json.loads(bc("state", "--json", project=p, data=d).stdout)
    assert j["rounds"] == ["r0"] and j["latest_round"] == "r0", j["latest_round"]
    assert _common.latest_round(p) == 0
    assert "rounds: r0   latest: r0" in bc("state", project=p, data=d).stdout
    (p / "rounds" / "r1").mkdir()
    j = json.loads(bc("state", "--json", project=p, data=d).stdout)
    assert j["rounds"] == ["r0", "r1"] and j["latest_round"] == "r1"
    assert "rounds: r0 r1   latest: r1" in bc("state", project=p, data=d).stdout


def test_state_parser_handles_quotes_comments_and_flow_values(tmp_path):
    f = tmp_path / "BRAND-STATE.md"
    f.write_text('---\nname: "A # not a comment"   # real comment\nlist: [1, 2]\nempty: ""\nmap: {}\n---\nbody\n')
    s = _common.State(f)
    assert s.data() == {"name": "A # not a comment", "list": ["1", "2"], "empty": "", "map": {}}
    s.set("map.k", "v")
    s.set("name", "New: value")
    s.save()
    d = _common.State(f).data()
    assert d["map"] == {"k": "v"} and d["name"] == "New: value"
    assert "# real comment" in f.read_text()


def test_state_remove_drops_a_top_level_key_with_its_children_and_nothing_else(tmp_path):
    f = tmp_path / "BRAND-STATE.md"
    f.write_text("---\nname: x\nmap:\n  a: 1\n  b: 2\nafter: y   # keep\n---\nbody\n")
    s = _common.State(f)
    assert s.remove("nope") is False and s.remove("a") is False        # a nested key is not a top-level key
    assert s.remove("map") is True
    s.save()
    assert f.read_text() == "---\nname: x\nafter: y   # keep\n---\nbody\n"
    s = _common.State(f)
    assert s.remove("name") is True
    s.set("late", "1")                                                  # the frontmatter end moved with the removals
    s.save()
    assert _common.State(f).data() == {"after": "y", "late": "1"} and f.read_text().endswith("---\nbody\n")


# ---------------------------------------------------------------- g1s_round: written by `state --record G1s`, never by hand

STYLE_BOARD = ROOT / "tests" / "fixtures" / "style-board-filled.html"      # a finished style board: four territories


def _rounds(p, *names):
    for n in names:
        (p / "rounds" / n).mkdir(parents=True, exist_ok=True)


def _board(p, n, kind):
    """rounds/r<n>/board.html: a finished style board (kind 'style'), a stub that only says 'style', or a bare pick or refine board."""
    page = p / "rounds" / f"r{n}" / "board.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    if kind == "style":
        page.write_text(STYLE_BOARD.read_text(encoding="utf-8").replace('data-round="0"', f'data-round="{n}"'), encoding="utf-8")
    elif kind == "stub":
        page.write_text(f'<!doctype html><html><body data-round="{n}" data-board="style"></body></html>', encoding="utf-8")
    else:
        page.write_text(f'<!doctype html><html><body data-round="{n}" data-board="{kind}"><p>x</p></body></html>', encoding="utf-8")
    return page


def _has_g1s_round(p):
    """Is there a g1s_round key line? (The template carries a comment line that names it; that is not a key.)"""
    return re.search(r"(?m)^g1s_round:", (p / "BRAND-STATE.md").read_text()) is not None


def test_record_g1s_writes_the_highest_round_whose_board_is_a_style_board_and_r0_counts(tmp_path):
    p, d = make_project(tmp_path), tmp_path / "d"
    _board(p, 0, "style")
    r = bc("state", "--record", "G1s", "picked Harbor", project=p, data=d)
    assert r.returncode == 0 and "g1s_round = 0" in r.stdout and "recorded G1s" in r.stdout, r.stdout
    assert bc("state", "--get", "g1s_round", project=p, data=d).stdout.strip() == "0"
    _board(p, 1, "pick")
    _board(p, 3, "style")                                              # a gap in the numbers, folders that are not rounds, and a pick board above
    _rounds(p, "notes", "r2.bak")
    _board(p, 4, "pick")
    r = bc("state", "--record", "G1s", "picked Ember", project=p, data=d)
    assert r.returncode == 0 and "g1s_round = 3" in r.stdout
    assert bc("state", "--get", "g1s_round", project=p, data=d).stdout.strip() == "3"
    text = (p / "BRAND-STATE.md").read_text()
    assert len(re.findall(r"(?m)^g1s_round:", text)) == 1               # replaced, never repeated
    st = _common.State(p / "BRAND-STATE.md").data()
    assert st["g1s_round"] == "3" and st["gates"]["G1s"].endswith("picked Ember") and list(st["gates"])[2] == "G1s"
    # another gate leaves it alone, and so does a later style board
    _board(p, 5, "style")
    assert bc("state", "--record", "G2", "picked Harbor", project=p, data=d).returncode == 0
    assert bc("state", "--get", "g1s_round", project=p, data=d).stdout.strip() == "3"


def test_record_g1s_with_no_style_board_on_disk_removes_the_key_and_writes_none(tmp_path):
    p, d = make_project(tmp_path), tmp_path / "d"
    r = bc("state", "--record", "G1s", "skipped by owner", project=p, data=d)               # no rounds folder at all
    assert r.returncode == 0 and "g1s_round" not in r.stdout and not _has_g1s_round(p)
    assert bc("state", "--get", "g1s_round", project=p, data=d).returncode == 1
    _board(p, 1, "pick")                                                                     # a pick board is not a style board
    r = bc("state", "--record", "G1s", "picked Harbor", project=p, data=d)
    assert r.returncode == 0 and "g1s_round" not in r.stdout and not _has_g1s_round(p)
    _board(p, 0, "style")
    assert bc("state", "--record", "G1s", "picked Harbor", project=p, data=d).returncode == 0
    assert bc("state", "--get", "g1s_round", project=p, data=d).stdout.strip() == "0"
    before = (p / "BRAND-STATE.md").read_text()
    (p / "rounds").rename(tmp_path / "rounds-moved")                                         # the rounds are gone: an empty rounds/ folder
    (p / "rounds").mkdir()
    r = bc("state", "--record", "G1s", "picked Ember", project=p, data=d)
    assert r.returncode == 0 and "g1s_round removed (no style board on disk)" in r.stdout, r.stdout
    after = (p / "BRAND-STATE.md").read_text()
    assert not _has_g1s_round(p) and bc("state", "--get", "g1s_round", project=p, data=d).returncode == 1
    assert [ln for ln in before.split("\n") if not ln.startswith(("g1s_round:", "  G1s"))] == [ln for ln in after.split("\n") if not ln.startswith("  G1s")]
    assert _common.State(p / "BRAND-STATE.md").data()["gates"]["G1s"].endswith("picked Ember")   # the rest of the file is as it was
    # and a record with a stale key but no rounds folder at all
    st = _common.State(p / "BRAND-STATE.md")
    st.set("g1s_round", 9)
    st.save()
    (p / "rounds").rmdir()
    assert _has_g1s_round(p)
    assert bc("state", "--record", "G1s", "again", project=p, data=d).returncode == 0
    assert not _has_g1s_round(p)


NOT_A_STYLE_BOARD = {   # what round 2 holds when the pick is recorded -> it must not count as the style board the pick should follow
    "an empty folder": lambda p: _rounds(p, "r2"),
    "a folder with other files only": lambda p: (_rounds(p, "r2"), (p / "rounds/r2/notes.md").write_text("x")),
    "a copy of the pick board (cp -R rounds/r1 rounds/r2)": lambda p: shutil.copytree(p / "rounds" / "r1", p / "rounds" / "r2"),
    "a refine board": lambda p: _board(p, 2, "refine"),
    "a stub that only says style": lambda p: _board(p, 2, "stub"),
    "a style board with three territories": lambda p: mutate(_board(p, 2, "style"), 'data-section="territory" data-name="Meadow"', 'data-x="territory" data-name="Meadow"'),
    "a style board with no marker": lambda p: _board(p, 2, "style").write_text(STYLE_BOARD.read_text(encoding="utf-8").replace(' data-round="0" data-board="style"', "")),
    "a board.html that is a folder": lambda p: (p / "rounds/r2/board.html").mkdir(parents=True),
    "the html tag says style, the body says pick": lambda p: _board(p, 2, "style").write_text(STYLE_BOARD.read_text(encoding="utf-8").replace(
        '<html lang="en">', '<html lang="en" data-board="style">').replace('data-round="0" data-board="style"', 'data-round="2" data-board="pick"')),
}


@pytest.mark.parametrize("what", sorted(NOT_A_STYLE_BOARD))
def test_a_pick_recorded_before_the_style_board_of_the_next_round_is_written_does_not_look_newer(tmp_path, what):
    """The highest round folder used to be written. With r2 copied or created for the new style board, a pick recorded then (before the board was
    written) set g1s_round to 2, and the style gate took it as recorded after the board it had never seen (review case E3b)."""
    p, d = make_project(tmp_path), tmp_path / "d"
    _board(p, 1, "pick")
    NOT_A_STYLE_BOARD[what](p)
    assert (p / "rounds" / "r2").exists(), what
    r = bc("state", "--record", "G1s", "picked Ember", project=p, data=d)
    assert r.returncode == 0 and "g1s_round =" not in r.stdout and not _has_g1s_round(p), (what, r.stdout, r.stderr)
    # the real style board is written afterwards: the earlier record is still the older one, and a new record is the newer one
    shutil.rmtree(p / "rounds" / "r2")
    _board(p, 2, "style")
    assert not _has_g1s_round(p)
    r = bc("state", "--record", "G1s", "picked Ember", project=p, data=d)
    assert r.returncode == 0 and "g1s_round = 2" in r.stdout and bc("state", "--get", "g1s_round", project=p, data=d).stdout.strip() == "2"


def test_a_style_board_declared_on_the_html_tag_alone_counts(tmp_path):
    """The page's own element is the body, or the html tag when the body declares neither the round nor the kind."""
    p, d = make_project(tmp_path), tmp_path / "d"
    _board(p, 1, "pick")
    page = _board(p, 2, "style")
    page.write_text(page.read_text(encoding="utf-8").replace('<html lang="en">', '<html lang="en" data-round="2" data-board="style">').replace(
        '<body data-round="2" data-board="style">', "<body>"), encoding="utf-8")
    assert bc("state", "--record", "G1s", "picked Ember", project=p, data=d).returncode == 0
    assert bc("state", "--get", "g1s_round", project=p, data=d).stdout.strip() == "2"


@pytest.mark.parametrize("flag,arg", [("--set", "g1s_round=5"), ("--bump", "g1s_round")])
def test_g1s_round_cannot_be_set_or_bumped_by_hand(tmp_path, flag, arg):
    p, d = make_project(tmp_path), tmp_path / "d"
    _board(p, 1, "style")
    assert bc("state", "--record", "G1s", "picked Harbor", project=p, data=d).returncode == 0
    before = (p / "BRAND-STATE.md").read_bytes()
    r = bc("state", flag, arg, "--set", "tier=full", project=p, data=d)
    assert r.returncode == 2 and "written by --record G1s" in r.stderr, r.stderr
    assert (p / "BRAND-STATE.md").read_bytes() == before                                      # nothing was saved, not even the tier
    assert bc("state", "--get", "g1s_round", project=p, data=d).stdout.strip() == "1"
    # a project that has no key yet cannot be given one either
    p2 = make_project(tmp_path, slug="second")
    r = bc("state", flag, arg, project=p2, data=d)
    assert r.returncode == 2 and "written by --record G1s" in r.stderr
    assert not _has_g1s_round(p2)
    assert bc("state", "--set", "gates.G1s=x", project=p2, data=d).returncode == 2            # gates are refused the same way


# ---------------------------------------------------------------- freeze

def _project_with_round(tmp_path, g3=True):
    p = make_project(tmp_path)
    (p / "rounds" / "r3" / "assets").mkdir(parents=True)
    (p / "rounds" / "r3" / "board.html").write_text("<!doctype html><title>r3</title><p>approved</p>\n")
    (p / "rounds" / "r3" / "assets" / "mark.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>')
    if g3:
        assert bc("state", "--record", "G3", "approved r3", project=p, data=tmp_path / "d").returncode == 0
    return p


def test_freeze_requires_g3(tmp_path):
    p = _project_with_round(tmp_path, g3=False)
    r = bc("freeze", "r3", "--name", "approved", "--whole", project=p, data=tmp_path / "d")
    assert r.returncode == 1 and "G3" in r.stderr
    assert not (p / "history").exists()


def test_freeze_copies_banners_and_writes_the_manifest(tmp_path):
    p = _project_with_round(tmp_path)
    r = bc("freeze", "r3", "--name", "approved-board", "--whole", project=p, data=tmp_path / "d")
    assert r.returncode == 0, r.stderr
    dest = p / "history" / "2026-10-17-approved-board"
    html = (dest / "board.html").read_text()
    assert html.startswith("<!-- KEPT AS WRITTEN: frozen from rounds/r3 on 2026-10-17")
    assert html.endswith("<p>approved</p>\n")
    assert (dest / "assets" / "mark.svg").read_text() == (p / "rounds" / "r3" / "assets" / "mark.svg").read_text()
    assert "Kept as written" in (dest / "FROZEN.md").read_text()
    lines = (p / "history" / "MANIFEST.sha256").read_text().splitlines()
    assert [ln.split("  ")[1] for ln in lines] == sorted(ln.split("  ")[1] for ln in lines)
    assert {ln.split("  ")[1] for ln in lines} == {"2026-10-17-approved-board/FROZEN.md", "2026-10-17-approved-board/assets/mark.svg",
                                                    "2026-10-17-approved-board/board.html"}
    for ln in lines:  # the sha256sum format
        h, name = ln.split("  ")
        assert _common.sha256_file(p / "history" / name) == h
    assert _common.verify_history(p) == []


def test_freeze_refuses_to_overwrite_and_accepts_a_second_name(tmp_path):
    p = _project_with_round(tmp_path)
    assert bc("freeze", "3", "--name", "one", "--whole", project=p, data=tmp_path / "d").returncode == 0
    r = bc("freeze", "r3", "--name", "one", "--whole", project=p, data=tmp_path / "d")
    assert r.returncode == 1 and "never overwrites" in r.stderr
    assert bc("freeze", "r3", "--name", "two", "--whole", project=p, data=tmp_path / "d").returncode == 0
    assert len((p / "history" / "MANIFEST.sha256").read_text().splitlines()) == 6


def test_freeze_refuses_when_history_was_tampered_with(tmp_path):
    p = _project_with_round(tmp_path)
    assert bc("freeze", "r3", "--name", "one", "--whole", project=p, data=tmp_path / "d").returncode == 0
    victim = p / "history" / "2026-10-17-one" / "board.html"
    mutate(victim, "approved", "tampered")
    r = bc("freeze", "r3", "--name", "two", "--whole", project=p, data=tmp_path / "d")
    assert r.returncode == 1 and "not intact" in r.stderr and "modified" in r.stderr
    assert not (p / "history" / "2026-10-17-two").exists()


def test_freeze_validates_input(tmp_path):
    p = _project_with_round(tmp_path)
    assert bc("freeze", "r9", "--name", "x", project=p, data=tmp_path / "d").returncode == 1
    assert bc("freeze", "r3", "--name", "Bad Name", project=p, data=tmp_path / "d").returncode == 2
    (p / "rounds" / "r3" / "link").symlink_to(p / "BRAND-STATE.md")
    r = bc("freeze", "r3", "--name", "x", "--whole", project=p, data=tmp_path / "d")
    assert r.returncode == 1 and "symlink" in r.stderr


def test_path_confinement(tmp_path):
    p = make_project(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(_common.CliError) as e:
        _common.confine(p, outside / "x.txt")
    assert e.value.code == 2
    with pytest.raises(_common.CliError):
        _common.confine(p, "../escape.txt")
    (p / "sneaky").symlink_to(outside)
    with pytest.raises(_common.CliError):
        _common.confine(p, "sneaky/x.txt")
    assert _common.confine(p, "assets/new/x.txt") == Path(os.path.realpath(p)) / "assets" / "new" / "x.txt"


def test_a_refused_path_says_writes_unless_the_caller_only_reads_it(tmp_path):
    """The refusal ends "brand-creator only writes inside the project" for a path that may be written; a caller that only reads the path (read=True) is told "only reads", and the rest is the same."""
    p = make_project(tmp_path)
    outside = tmp_path / "outside" / "x.png"
    root = Path(os.path.realpath(p))
    with pytest.raises(_common.CliError) as w:
        _common.confine(p, outside, what="report")
    with pytest.raises(_common.CliError) as r:
        _common.confine(p, outside, what="site still", read=True)
    assert w.value.message == f"report {outside} is outside the project {root}; brand-creator only writes inside the project"
    assert r.value.message == f"site still {outside} is outside the project {root}; brand-creator only reads inside the project"
    assert w.value.code == r.value.code == 2
    assert _common.confine(p, "assets/x.png", read=True) == root / "assets" / "x.png", "a path inside the project is resolved the same for a read"


# ---- review finding S4: enum keys are validated, nothing is written on a bad value

@pytest.mark.parametrize("key,bad", [
    ("tier", "huge"), ("tier", "standrad"), ("tier", "Full "), ("tier", "FULL"), ("tier", ""),
    ("architecture", "galaxy"), ("mark_source", "traced"), ("review_surface", "email"),
    ("phase", "P5; rm"), ("phase", "P14"), ("phase", "p5"), ("phase", "5"), ("phase", "P1bb"), ("phase", ""),
])
def test_state_set_rejects_values_outside_the_enum(tmp_path, key, bad):
    p = make_project(tmp_path)
    before = (p / "BRAND-STATE.md").read_text()
    r = bc("state", "--set", f"{key}={bad}", project=p)
    assert r.returncode == 2, (key, bad, r.stdout, r.stderr)
    assert key in r.stderr and ("one of" in r.stderr or "P0 to P13" in r.stderr)
    assert (p / "BRAND-STATE.md").read_text() == before  # unchanged on error


def test_state_set_accepts_every_documented_value(tmp_path):
    p = make_project(tmp_path)
    vals = {"tier": ("quick", "standard", "full"), "architecture": ("standalone", "family-member", "product-in-family"),
            "mark_source": ("generated", "authored-vector", "existing"), "review_surface": ("auto", "artifact", "local"),
            "phase": tuple(f"P{i}" for i in range(14)) + ("P1b", "P1c")}
    for key, options in vals.items():
        for v in options:
            r = bc("state", "--set", f"{key}={v}", project=p)
            assert r.returncode == 0, (key, v, r.stderr)
            assert bc("state", "--get", key, project=p).stdout.strip() == v


# ---- the site work's two gates (G4w website references, G4p the site's reference pages) and the site_research answer

def test_state_records_and_requires_the_website_gates(tmp_path):
    p = make_project(tmp_path)
    r = bc("state", "--require", "G4p", project=p)
    assert r.returncode == 1 and "G4p" in r.stderr and "--record" in r.stderr, r.stderr
    assert bc("state", "--require", "G4w", project=p).returncode == 1
    r = bc("state", "--record", "G4w", "skipped by owner", project=p)
    assert r.returncode == 0 and "recorded G4w: 2026-10-17 skipped by owner" in r.stdout, r.stdout + r.stderr
    r = bc("state", "--require", "G4w", project=p)
    assert r.returncode == 0 and "G4w: recorded (2026-10-17 skipped by owner)" in r.stdout, r.stdout + r.stderr
    assert bc("state", "--require", "G4p", project=p).returncode == 1                       # recording one gate leaves the other open
    out = bc("state", project=p).stdout
    assert "gates: G0 -  G1 -  G1s -  G2 -  G2b -  G3 -  G4 -  G4w recorded  G4p -  G5 -  G6 -  G7 -" in out, out
    assert "  G4w: 2026-10-17 skipped by owner" in out
    assert bc("state", "--record", "G4p", "approved start, pricing", project=p).returncode == 0
    out = bc("state", project=p).stdout
    assert "G4 -  G4w recorded  G4p recorded  G5 -" in out
    assert out.index("  G4w: ") < out.index("  G4p: ")                                         # the detail lines keep the gate order too
    gates = json.loads(bc("state", "--json", project=p).stdout)["state"]["gates"]
    assert list(gates) == ["G0", "G1", "G1s", "G2", "G2b", "G3", "G4", "G4w", "G4p", "G5", "G6", "G7"]
    assert gates["G4p"] == "2026-10-17 approved start, pricing"
    r = bc("state", "--record", "G4x", "nope", project=p)
    assert r.returncode == 2 and "G4w, G4p" in r.stderr, r.stderr                           # the refusal lists the gates in order
    assert bc("state", "--set", "gates.G4w=x", project=p).returncode == 2                   # a gate is only written by --record


def test_site_research_takes_only_its_four_answers(tmp_path):
    p = make_project(tmp_path)
    assert re.match(r"site_research: auto(\s+#.*)?$", _state_line(p, "site_research")), _state_line(p, "site_research")   # the template starts at "not asked"
    for answer in ("online", "links-only", "none", "auto"):
        r = bc("state", "--set", f"site_research={answer}", project=p)
        assert r.returncode == 0, (answer, r.stderr)
        assert bc("state", "--get", "site_research", project=p).stdout.strip() == answer
    assert bc("state", "--set", "site_research=links-only", project=p).returncode == 0
    before = (p / "BRAND-STATE.md").read_bytes()
    for bad in ("yes", "offline", "Online", "links_only", ""):
        r = bc("state", "--set", f"site_research={bad}", project=p)
        assert r.returncode == 2, (bad, r.stdout, r.stderr)
        assert "site_research must be one of auto | online | links-only | none" in r.stderr, r.stderr
        assert (p / "BRAND-STATE.md").read_bytes() == before                                 # nothing written
    r = bc("state", "--set", "tier=full", "--set", "site_research=yes", project=p)           # one bad value refuses the whole call
    assert r.returncode == 2 and (p / "BRAND-STATE.md").read_bytes() == before


def test_an_older_project_without_the_website_gates_gets_them_on_record(tmp_path):
    p = make_project(tmp_path)
    state = p / "BRAND-STATE.md"
    text = state.read_text(encoding="utf-8")
    for gate in ("G4w", "G4p"):                                                              # a project made before the site work: no such lines
        mutate(state, re.search(rf"(?m)^  {gate}:.*\n", text).group(0), "")
    mutate(state, re.search(r"(?m)^site_research:.*\n", text).group(0), "")
    assert "G4w" not in state.read_text(encoding="utf-8") and "site_research" not in state.read_text(encoding="utf-8")
    out = bc("state", project=p)
    assert out.returncode == 0 and "G4 -  G4w -  G4p -  G5 -" in out.stdout, out.stdout + out.stderr   # it still reads, both gates open
    assert bc("state", "--require", "G4w", project=p).returncode == 1
    assert bc("state", "--get", "site_research", project=p).returncode == 1
    assert bc("state", "--record", "G4w", "skipped by owner", project=p).returncode == 0
    assert bc("state", "--record", "G4p", "approved start", project=p).returncode == 0
    assert bc("state", "--set", "site_research=online", project=p).returncode == 0
    data = _common.State(state).data()
    assert data["gates"]["G4w"] == "2026-10-17 skipped by owner" and data["gates"]["G4p"] == "2026-10-17 approved start", data["gates"]
    assert data["site_research"] == "online" and data["gates"]["G3"] == "" and data["gates"]["G5"] == ""
    assert "G4 -  G4w recorded  G4p recorded  G5 -" in bc("state", project=p).stdout


def test_a_tryout_url_is_a_key_of_its_own_apart_from_the_review_url(tmp_path):
    """G4-17: the private page a shared try-out is on is `tryout_url`; `review_url` stays the one review page of the boards. Setting one never touches the other, the summary shows the try-out
    page only while it is set, a project made before the key gets it on its first --set, and writing it leaves the G4 rules a page check holds (`--part g4-rules`) as they were."""
    p = make_project(tmp_path)
    assert re.match(r'tryout_url: ""(\s+#.*)?$', _state_line(p, "tryout_url")), _state_line(p, "tryout_url")        # the template carries the key, empty
    review, tryout = "https://claude.example.invalid/artifact/review?v=1#top", "https://claude.example.invalid/artifact/atlas?v=2#top"
    assert bc("state", "--set", f"review_url={review}", project=p).returncode == 0
    rules = bc("state", "--part", "g4-rules", project=p).stdout
    assert "try-out url" not in bc("state", project=p).stdout, "nothing to show while the key is empty"
    r = bc("state", "--set", f"tryout_url={tryout}", project=p)
    assert r.returncode == 0, r.stderr
    assert bc("state", "--get", "tryout_url", project=p).stdout.strip() == tryout
    assert bc("state", "--get", "review_url", project=p).stdout.strip() == review, "the review page is the one it was"
    out = bc("state", project=p).stdout
    assert f"review url: {review}" in out and f"try-out url: {tryout}" in out, out
    data = json.loads(bc("state", "--json", project=p).stdout)["state"]
    assert data["tryout_url"] == tryout and data["review_url"] == review
    assert bc("state", "--part", "g4-rules", project=p).stdout == rules, "a page check holds the G4 rules only: this write leaves its reports current"
    r = bc("state", "--set", f"review_url={review}x", project=p)                                                      # the other way round
    assert r.returncode == 0 and bc("state", "--get", "tryout_url", project=p).stdout.strip() == tryout
    assert bc("state", "--set", "tryout_url=", project=p).returncode == 0                                            # cleared at the stage gate
    assert bc("state", "--get", "tryout_url", project=p).stdout.strip() == "" and "try-out url" not in bc("state", project=p).stdout
    assert bc("state", "--get", "review_url", project=p).stdout.strip() == review + "x"
    # a project made before the key: no such line, it still reads, and the first --set adds the key
    state = p / "BRAND-STATE.md"
    state.write_text(re.sub(r"(?m)^tryout_url:.*\n", "", state.read_text(encoding="utf-8")), encoding="utf-8")
    assert "tryout_url" not in state.read_text(encoding="utf-8") and bc("state", project=p).returncode == 0
    assert bc("state", "--get", "tryout_url", project=p).returncode == 1
    assert bc("state", "--set", f"tryout_url={tryout}", project=p).returncode == 0
    assert _common.State(state).data()["tryout_url"] == tryout and _common.State(state).data()["review_url"] == review + "x"


def test_state_set_is_all_or_nothing_when_one_value_is_bad(tmp_path):
    p = make_project(tmp_path)
    before = (p / "BRAND-STATE.md").read_text()
    r = bc("state", "--set", "tier=full", "--set", "architecture=galaxy", project=p)
    assert r.returncode == 2 and (p / "BRAND-STATE.md").read_text() == before
    assert bc("state", "--get", "tier", project=p).stdout.strip() == "quick"


# ---- list keys: `state --set` writes a real YAML flow list, and reset_rounds is read through one helper

def _state_line(p, key):
    m = re.search(rf"(?m)^{key}:.*$", (p / "BRAND-STATE.md").read_text())
    return m.group(0) if m else None


@pytest.mark.parametrize("given,written,rounds", [
    ("[2,3]", "[2, 3]", [2, 3]), ("[2, 3]", "[2, 3]", [2, 3]), ("2,3", "[2, 3]", [2, 3]), ("2", "[2]", [2]),
    ("[10,11]", "[10, 11]", [10, 11]), ("[10, 11, 12]", "[10, 11, 12]", [10, 11, 12]), ("[02]", "[2]", [2]),
    ("[]", "[]", []), ("", "[]", []), ("[ ]", "[]", []),
])
def test_state_set_writes_reset_rounds_as_a_real_list(tmp_path, given, written, rounds):
    """It was saved as the quoted string "[2,3]", which board-lint then read one character at a time ("[10,11]" became 1, 0, 1, 1)."""
    p = make_project(tmp_path)
    r = bc("state", "--set", f"reset_rounds={given}", project=p)
    assert r.returncode == 0, r.stderr
    line = _state_line(p, "reset_rounds")
    assert re.match(rf"reset_rounds: {re.escape(written)}(\s+#.*)?$", line), line         # a flow list, never a quoted string
    st = _common.State(p / "BRAND-STATE.md")
    assert st.data()["reset_rounds"] == [str(n) for n in rounds] and st.reset_rounds() == rounds
    assert json.loads(bc("state", "--get", "reset_rounds", project=p).stdout) == [str(n) for n in rounds]
    assert bc("state", "--set", f"reset_rounds={given}", project=p).returncode == 0      # setting it again replaces the line, never repeats it
    assert len(re.findall(r"(?m)^reset_rounds:", (p / "BRAND-STATE.md").read_text())) == 1


@pytest.mark.parametrize("bad", ["[0]", "[-1]", "[1.5]", "[a]", "[2,,3]", "[1, x]", "[2,3", "2 3", "[[2]]", "0", "-2", "[2;3]", "two", "[2, 0]"])
def test_state_set_refuses_reset_rounds_that_are_not_whole_numbers_from_1(tmp_path, bad):
    p = make_project(tmp_path)
    before = (p / "BRAND-STATE.md").read_text()
    r = bc("state", "--set", f"reset_rounds={bad}", "--set", "tier=full", project=p)
    assert r.returncode == 2 and "reset_rounds" in r.stderr and "whole numbers from 1" in r.stderr, (bad, r.stdout, r.stderr)
    assert (p / "BRAND-STATE.md").read_text() == before                                  # nothing is written, not even the tier


@pytest.mark.parametrize("kv,line", [("reset_rounds =2,3", "reset_rounds: [2, 3]"), (" reset_rounds = [2, 3] ", "reset_rounds: [2, 3]"),
                                     ("tier =standard", "tier: standard")])
def test_state_set_trims_the_spaces_around_the_key_and_the_value(tmp_path, kv, line):
    """Review case E11. "reset_rounds =2,3" skipped the list check and wrote the key `reset_rounds `; the state then no longer read."""
    p = make_project(tmp_path)
    assert bc("state", "--set", kv, project=p).returncode == 0
    assert _state_line(p, line.split(":")[0]).startswith(line)
    assert bc("state", project=p).returncode == 0


@pytest.mark.parametrize("kv", ["g1s_round =9", "reset rounds=2", "=2", " =2", "tier:x=full", "#tier=full"])
def test_state_set_refuses_a_key_that_is_not_one_word(tmp_path, kv):
    p = make_project(tmp_path)
    before = (p / "BRAND-STATE.md").read_text()
    r = bc("state", "--set", kv, project=p)
    assert r.returncode == 2, (kv, r.stdout, r.stderr)
    assert (p / "BRAND-STATE.md").read_text() == before


def test_state_set_writes_book_chapters_as_a_real_list_too(tmp_path):
    p = make_project(tmp_path)
    for given, written, items in (("tone", "[tone]", ["tone"]), ("tone,photography", "[tone, photography]", ["tone", "photography"]),
                                  ("[tone, photography]", "[tone, photography]", ["tone", "photography"]), ("['tone']", "[tone]", ["tone"]),
                                  ("[]", "[]", [])):
        assert bc("state", "--set", f"book_chapters={given}", project=p).returncode == 0, given
        assert re.match(rf"book_chapters: {re.escape(written)}(\s+#.*)?$", _state_line(p, "book_chapters")), (given, _state_line(p, "book_chapters"))
        assert _common.State(p / "BRAND-STATE.md").data()["book_chapters"] == items
    before = (p / "BRAND-STATE.md").read_text()
    for bad in ("[to ne]", "[a#b]", "[tone;x]"):
        r = bc("state", "--set", f"book_chapters={bad}", project=p)
        assert r.returncode == 2 and "book_chapters" in r.stderr and (p / "BRAND-STATE.md").read_text() == before, bad


def test_every_list_key_of_the_state_template_is_written_as_a_list_by_set(tmp_path):
    """A key the template holds as `key: [...]` must never be left to --set as a string: a new list key goes into LIST_KEYS in state.py."""
    keys = re.findall(r"(?m)^([a-z_]+): \[", (ROOT / "templates" / "BRAND-STATE.md").read_text(encoding="utf-8"))
    assert {"reset_rounds", "book_chapters"} <= set(keys), keys
    p = make_project(tmp_path)
    for k in keys:
        assert bc("state", "--set", f"{k}=1", project=p).returncode == 0, k
        assert re.match(rf"{k}: \[1\](\s+#.*)?$", _state_line(p, k)), (k, _state_line(p, k))


@pytest.mark.parametrize("stored,rounds", [
    ("[10, 11]", [10, 11]), ('"[10,11]"', [10, 11]), ('"[2,3]"', [2, 3]), ('"[2, 3]"', [2, 3]), ("[2]", [2]), ('"[4]"', [4]), ('"[]"', []),
    ("[]", []), ('""', []), ("", []), ("2", [2]), ('"2,3"', [2, 3]), ("[x, 3]", [3]), ("{}", []),
])
def test_reset_rounds_is_read_through_one_helper_that_takes_a_list_or_the_old_quoted_string(tmp_path, stored, rounds):
    f = tmp_path / "BRAND-STATE.md"
    f.write_text(f"---\nslug: x\nreset_rounds: {stored}\n---\n")
    assert _common.State(f).reset_rounds() == rounds
    f.write_text("---\nslug: x\n---\n")
    assert _common.State(f).reset_rounds() == []                                         # a project without the key


def test_raising_the_tier_on_a_hand_authored_book_reads_chapter_attributes_and_survives_a_broken_config(tmp_path):
    p = make_project(tmp_path, slug="hand", tier="standard")
    assert bc("state", "--set", "mark_source=authored-vector", project=p).returncode == 0
    (p / "book").mkdir(exist_ok=True)
    (p / "book" / "book.json").write_text("{not json")
    r = bc("state", "--set", "tier=full", project=p)
    assert r.returncode == 0, r.stderr
    assert "not checked" in r.stdout and "book.json" in r.stdout
    (p / "book" / "book.json").write_text("{}")
    out = (p / "book.html")
    out.write_text("<section data-chapter='adoption'></section><section data-chapter=\"launch\"></section>")
    r = bc("state", "--set", "tier=quick", project=p)
    r = bc("state", "--set", "tier=full", project=p)
    assert "adoption" not in r.stdout.split("INVENTORY.md")[0].split("(in the book)")[-1] and "launch" not in r.stdout.split("(in the book)")[-1].split("INVENTORY.md")[0]


def test_raising_the_tier_still_names_the_inventory_when_book_json_cannot_be_read(tmp_path):
    p = make_project(tmp_path, tier="quick")
    for kv in ("content_languages=pl", "mark_source=authored-vector"):
        assert bc("state", "--set", kv, project=p).returncode == 0
    (p / "book").mkdir(exist_ok=True)
    (p / "book" / "book.json").write_text("{bad")
    r = bc("state", "--set", "tier=full", project=p)
    assert r.returncode == 0, r.stderr
    assert "book/book.json cannot be read" in r.stdout and "INVENTORY.md" in r.stdout, r.stdout
