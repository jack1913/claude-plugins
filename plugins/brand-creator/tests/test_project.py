"""new, state, freeze, project discovery and path confinement."""
import json
import os
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
    assert list(st["gates"]) == ["G0", "G1", "G2", "G2b", "G3", "G4", "G5", "G6", "G7"]
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
