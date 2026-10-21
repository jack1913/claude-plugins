"""new, state, freeze, project discovery and path confinement."""
import json
import os
import re
import shutil
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
    assert list(st["gates"]) == ["G0", "G1", "G1s", "G2", "G2b", "G3", "G4", "G5", "G6", "G7"]
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
    r = bc("freeze", "r3", "--name", "approved", project=p, data=tmp_path / "d")
    assert r.returncode == 1 and "G3" in r.stderr
    assert not (p / "history").exists()


def test_freeze_copies_banners_and_writes_the_manifest(tmp_path):
    p = _project_with_round(tmp_path)
    r = bc("freeze", "r3", "--name", "approved-board", project=p, data=tmp_path / "d")
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
    assert bc("freeze", "3", "--name", "one", project=p, data=tmp_path / "d").returncode == 0
    r = bc("freeze", "r3", "--name", "one", project=p, data=tmp_path / "d")
    assert r.returncode == 1 and "never overwrites" in r.stderr
    assert bc("freeze", "r3", "--name", "two", project=p, data=tmp_path / "d").returncode == 0
    assert len((p / "history" / "MANIFEST.sha256").read_text().splitlines()) == 6


def test_freeze_refuses_when_history_was_tampered_with(tmp_path):
    p = _project_with_round(tmp_path)
    assert bc("freeze", "r3", "--name", "one", project=p, data=tmp_path / "d").returncode == 0
    victim = p / "history" / "2026-10-17-one" / "board.html"
    mutate(victim, "approved", "tampered")
    r = bc("freeze", "r3", "--name", "two", project=p, data=tmp_path / "d")
    assert r.returncode == 1 and "not intact" in r.stderr and "modified" in r.stderr
    assert not (p / "history" / "2026-10-17-two").exists()


def test_freeze_validates_input(tmp_path):
    p = _project_with_round(tmp_path)
    assert bc("freeze", "r9", "--name", "x", project=p, data=tmp_path / "d").returncode == 1
    assert bc("freeze", "r3", "--name", "Bad Name", project=p, data=tmp_path / "d").returncode == 2
    (p / "rounds" / "r3" / "link").symlink_to(p / "BRAND-STATE.md")
    r = bc("freeze", "r3", "--name", "x", project=p, data=tmp_path / "d")
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
