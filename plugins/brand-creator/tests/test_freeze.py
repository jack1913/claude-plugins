"""freeze keeps what the round's boards show and the scripts that built it (closure), or everything (--whole), or the closure read
from the files only (--static). The copy is checked in the browser before it becomes history."""
from __future__ import annotations

import pytest

from helpers import bc, data_dir, make_project, own_data
import closure

FROZEN = "history/2026-10-17-approved"


def mkd(d):
    d.mkdir()
    return d
PNG = b"\x89PNG\r\n\x1a\n"


def project_with_round(tmp_path, files: dict[str, str | bytes]):
    p = make_project(tmp_path)
    for rel, data in files.items():
        f = p / "rounds" / "r3" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data.encode() if isinstance(data, str) else data)
    assert bc("state", "--record", "G3", "approved r3", project=p, data=tmp_path / "nodata").returncode == 0
    return p


def frozen_files(p) -> list[str]:
    root = p / FROZEN
    return sorted(f.relative_to(root).as_posix() for f in root.rglob("*") if f.is_file())


ROUND = {"board.html": '<img src="shots/a.png">', "shots/a.png": PNG, "_lead/shots/big.png": PNG * 100, "build.py": "print(1)\n"}


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_freeze_keeps_the_boards_what_they_show_and_the_builders_and_leaves_the_rest(tmp_path):
    p = project_with_round(tmp_path, ROUND)
    r = bc("freeze", "r3", "--name", "approved", project=p, data=own_data(data_dir(), mkd(tmp_path / "d")))
    assert r.returncode == 0, r.stderr
    assert frozen_files(p) == ["FROZEN.md", "board.html", "build.py", "shots/a.png"]
    frozen = (p / FROZEN / "FROZEN.md").read_text()
    assert "mode: closure" in frozen and "left out: 1 files" in frozen and "_lead" in frozen
    assert "left out 1 files" in r.stdout


def test_freeze_whole_copies_everything_as_before(tmp_path):
    p = project_with_round(tmp_path, ROUND)
    r = bc("freeze", "r3", "--name", "approved", "--whole", project=p, data=tmp_path / "nodata")
    assert r.returncode == 0, r.stderr
    assert frozen_files(p) == ["FROZEN.md", "_lead/shots/big.png", "board.html", "build.py", "shots/a.png"]
    assert "mode: whole" in (p / FROZEN / "FROZEN.md").read_text()


def test_without_a_browser_freeze_stops_and_names_static(tmp_path):
    p = project_with_round(tmp_path, ROUND)
    r = bc("freeze", "r3", "--name", "approved", project=p, data=tmp_path / "nodata")
    assert r.returncode == 3, r.stderr
    assert "--static" in r.stderr and "--whole" in r.stderr
    assert not (p / "history").exists()


def test_freeze_static_keeps_what_the_files_reference_and_records_static(tmp_path):
    p = project_with_round(tmp_path, ROUND)
    r = bc("freeze", "r3", "--name", "approved", "--static", project=p, data=tmp_path / "nodata")
    assert r.returncode == 0, r.stderr
    assert frozen_files(p) == ["FROZEN.md", "board.html", "build.py", "shots/a.png"]
    assert "mode: static" in (p / FROZEN / "FROZEN.md").read_text()


def test_whole_and_static_refuse_each_other(tmp_path):
    p = project_with_round(tmp_path, ROUND)
    r = bc("freeze", "r3", "--name", "approved", "--whole", "--static", project=p, data=tmp_path / "nodata")
    assert r.returncode == 2 and "--whole" in r.stderr and "--static" in r.stderr


def test_a_round_with_no_board_page_needs_whole(tmp_path):
    p = project_with_round(tmp_path, {"notes.html": "<p>x</p>", "a.png": PNG})
    r = bc("freeze", "r3", "--name", "approved", "--static", project=p, data=tmp_path / "nodata")
    assert r.returncode == 1 and "--whole" in r.stderr and "board.html" in r.stderr
    assert not (p / "history").exists()


def test_a_reference_already_broken_in_the_round_is_listed_not_a_failure(tmp_path):
    p = project_with_round(tmp_path, {"board.html": '<img src="gone.png"><img src="a.png">', "a.png": PNG})
    r = bc("freeze", "r3", "--name", "approved", "--static", project=p, data=tmp_path / "nodata")
    assert r.returncode == 0, r.stderr
    assert "already missing in the round: board.html: gone.png" in (p / FROZEN / "FROZEN.md").read_text()
    assert "gone.png" in r.stdout


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_script_added_picture_is_frozen(tmp_path):
    board = '<div id="g"></div><script>const i = document.createElement("img"); i.src = "shots/" + "late" + ".png"; g.append(i);</script>'
    p = project_with_round(tmp_path, {"board.html": board, "shots/late.png": PNG, "shots/other.png": PNG})
    r = bc("freeze", "r3", "--name", "approved", project=p, data=own_data(data_dir(), mkd(tmp_path / "d")))
    assert r.returncode == 0, r.stderr
    assert frozen_files(p) == ["FROZEN.md", "board.html", "shots/late.png"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_the_copy_check_names_a_file_the_copy_lost(tmp_path, monkeypatch):
    src, copy = tmp_path / "src", tmp_path / "copy"
    for root in (src, copy):
        (root / "shots").mkdir(parents=True)
        (root / "board.html").write_text('<div id="g"></div><script>for (const n of [1, 2]) { const i = document.createElement("img"); '
                                         'i.src = "shots/" + n + ".png"; g.append(i); }</script>')
        (root / "shots" / "1.png").write_bytes(PNG)
    (src / "shots" / "2.png").write_bytes(PNG)
    monkeypatch.setenv("BRAND_CREATOR_DATA", str(data_dir()))
    assert closure.copy_losses(src, copy) == ["board.html: shots/2.png"]
    assert closure.copy_losses(src, src) == []


def test_a_motion_proof_no_board_links_is_still_frozen(tmp_path):
    p = project_with_round(tmp_path, {"board.html": '<img src="v1/still.png">', "v1/still.png": PNG, "v1/proof.json": '{"case": "a"}',
                                      "v1/unshown.png": PNG})
    r = bc("freeze", "r3", "--name", "approved", "--static", project=p, data=tmp_path / "nodata")
    assert r.returncode == 0, r.stderr
    assert frozen_files(p) == ["FROZEN.md", "board.html", "v1/proof.json", "v1/still.png"]
