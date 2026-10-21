"""patch (assert-counted replace, the one edit path of a hand-authored book) and collapse (take the losing variants out after a decision)."""
import json
import re
import shutil
import subprocess
import sys

import pytest
from helpers import ROOT, bc, make_project, mutate

import _common


@pytest.fixture
def proj(tmp_path):
    p = make_project(tmp_path, tier="standard")
    for kv in ("content_languages=en", "mark_source=authored-vector"):
        assert bc("state", "--set", kv, project=p).returncode == 0
    (p / "book.html").write_text("<!doctype html>\n<html lang=\"en\"><body>\n<p>alpha beta</p>\n<p>alpha gamma</p>\n</body></html>\n")
    return p


def state(p):
    return _common.State(p / "BRAND-STATE.md")


def log(p):
    return [ln for ln in (p / "BRAND-STATE.md").read_text().split("\n") if re.match(r"^- \d{4}-\d{2}-\d{2} edition ", ln)]


# ---------------------------------------------------------------- patch

def test_patch_refuses_a_wrong_count_and_writes_nothing(proj):
    before, st_before = (proj / "book.html").read_bytes(), (proj / "BRAND-STATE.md").read_bytes()
    r = bc("patch", "book.html", "--old", "alpha", "--new", "omega", "--count", "3", project=proj)
    assert r.returncode == 1 and "holds the text 2 time(s), --count says 3" in r.stderr
    assert (proj / "book.html").read_bytes() == before and (proj / "BRAND-STATE.md").read_bytes() == st_before
    r = bc("patch", "book.html", "--old", "no such text", "--new", "x", "--count", "1", project=proj)
    assert r.returncode == 1 and "holds the text 0 time(s)" in r.stderr


def test_patch_with_the_right_count_replaces_and_logs_the_edition(proj):
    r = bc("patch", "book.html", "--old", "alpha", "--new", "omega", "--count", "2", "--note", "rename", project=proj)
    assert r.returncode == 0, r.stderr
    assert (proj / "book.html").read_text().count("omega") == 2 and "alpha" not in (proj / "book.html").read_text()
    assert log(proj) == ["- 2026-10-17 edition 1: patched book.html (2 replacements): rename"]
    assert state(proj).get("edition") == "1"


def test_patch_on_a_file_that_is_not_the_book_writes_no_edition_log(proj):
    (proj / "notes.md").write_text("one two one\n")
    assert bc("patch", "notes.md", "--old", "one", "--new", "1", "--count", "2", project=proj).returncode == 0
    assert (proj / "notes.md").read_text() == "1 two 1\n" and log(proj) == []


def test_patch_takes_multi_line_text_from_files(proj, tmp_path):
    (tmp_path / "old.txt").write_text("<p>alpha beta</p>\n<p>alpha gamma</p>\n")
    (tmp_path / "new.txt").write_text("<p>one</p>\n")
    r = bc("patch", "book.html", "--old-file", str(tmp_path / "old.txt"), "--new-file", str(tmp_path / "new.txt"), "--count", "1", project=proj)
    assert r.returncode == 0, r.stderr
    assert "<p>one</p>\n</body>" in (proj / "book.html").read_text()


def test_patch_never_touches_history_earlier_rounds_or_paths_outside_the_project(proj, tmp_path):
    (proj / "history/2026-10-17-x").mkdir(parents=True)
    (proj / "history/2026-10-17-x/board.html").write_text("alpha")
    for r_ in (1, 2):
        (proj / f"rounds/r{r_}").mkdir(parents=True)
        (proj / f"rounds/r{r_}/board.html").write_text("alpha")
    r = bc("patch", "history/2026-10-17-x/board.html", "--old", "alpha", "--new", "b", "--count", "1", project=proj)
    assert r.returncode == 1 and "frozen" in r.stderr
    r = bc("patch", "rounds/r1/board.html", "--old", "alpha", "--new", "b", "--count", "1", project=proj)
    assert r.returncode == 1 and "earlier round" in r.stderr
    assert bc("patch", "rounds/r2/board.html", "--old", "alpha", "--new", "b", "--count", "1", project=proj).returncode == 0
    outside = tmp_path / "outside.txt"
    outside.write_text("alpha")
    r = bc("patch", str(outside), "--old", "alpha", "--new", "b", "--count", "1", project=proj)
    assert r.returncode == 2 and outside.read_text() == "alpha"


def _round_files(proj, *rounds):
    for r_ in rounds:
        (proj / f"rounds/r{r_}").mkdir(parents=True, exist_ok=True)
        (proj / f"rounds/r{r_}/board.html").write_text("alpha")


def _patch_edits(proj, rel_path):
    """Does `patch` edit the file? (It also puts the original text back, so the next question starts from the same file.)"""
    r = bc("patch", rel_path, "--old", "alpha", "--new", "b", "--count", "1", project=proj)
    assert r.returncode in (0, 1), r.stderr
    if r.returncode == 1:
        assert "earlier round" in r.stderr, r.stderr
    (proj / rel_path).write_text("alpha")
    return r.returncode == 0


def _hook_allows(proj, rel_path):
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(proj / rel_path)}})
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "guard.py")], input=payload, capture_output=True, text=True)
    assert r.returncode in (0, 2), r.stderr
    return r.returncode == 0


def test_patch_edits_round_0_while_g1s_is_empty_and_stops_when_it_is_recorded(proj):
    """The hook keeps rounds/r0/ (the style board) writable while G1s is empty, even with round 1 on disk. patch said 'is in an earlier round'."""
    _round_files(proj, 0, 1)
    assert not bc("state", "--get", "gates.G1s", project=proj).stdout.strip()
    r = bc("patch", "rounds/r0/board.html", "--old", "alpha", "--new", "b", "--count", "1", project=proj)
    assert r.returncode == 0, r.stderr
    assert (proj / "rounds/r0/board.html").read_text() == "b"
    assert bc("state", "--record", "G1s", "picked Harbor", project=proj).returncode == 0
    (proj / "rounds/r0/board.html").write_text("alpha")
    r = bc("patch", "rounds/r0/board.html", "--old", "alpha", "--new", "b", "--count", "1", project=proj)
    assert r.returncode == 1 and "earlier round" in r.stderr and (proj / "rounds/r0/board.html").read_text() == "alpha"
    assert bc("patch", "rounds/r1/board.html", "--old", "alpha", "--new", "b", "--count", "1", project=proj).returncode == 0   # r1 is the latest


def test_the_allowance_is_for_round_0_only_and_a_later_round_is_still_earlier(proj):
    _round_files(proj, 0, 1, 2)
    assert _patch_edits(proj, "rounds/r0/board.html") is True and _patch_edits(proj, "rounds/r2/board.html") is True
    r = bc("patch", "rounds/r1/board.html", "--old", "alpha", "--new", "b", "--count", "1", project=proj)
    assert r.returncode == 1 and "earlier round" in r.stderr and (proj / "rounds/r1/board.html").read_text() == "alpha"


# (state, rounds on disk) cases: patch and the hook must give the same answer for every round of every case
AGREEMENT_STATES = {
    "G1s empty": '---\nslug: x\ngates:\n  G1s: ""\n---\n',
    "G1s missing": '---\nslug: x\ngates:\n  G0: "x"\n---\n',
    "G1s recorded": '---\nslug: x\ngates:\n  G1s: "2026-10-17 picked Harbor"\n---\n',
    "G1s skipped": '---\nslug: x\ngates:\n  G1s: "2026-10-17 skipped by owner"\n---\n',
    "a tab-indented line": '---\nslug: x\ngates:\n\tG1s: ""\n---\n',
    "a quoted key": '---\nslug: x\ngates:\n  "G1s": ""\n---\n',
    "a flow map": '---\nslug: x\ngates: {G1s: ""}\n---\n',
    "no gates at all": "---\nslug: x\n---\n",
    "an indented line under a plain value": '---\nslug: x\nname: Acme\n  note: y\ngates:\n  G1s: ""\n---\n',
    "an indented line before the first key": '---\n  note: y\nslug: x\ngates:\n  G1s: ""\n---\n',
}


@pytest.mark.parametrize("why", sorted(AGREEMENT_STATES))
def test_patch_and_the_hook_give_the_same_answer_for_every_round(proj, why):
    """One rule, one function (guard.round_is_open): they cannot drift. Checked on the real hook and the real patch command."""
    _round_files(proj, 0, 1, 2)
    (proj / "BRAND-STATE.md").write_text(AGREEMENT_STATES[why])
    answers = {r_: (_hook_allows(proj, f"rounds/r{r_}/board.html"), _patch_edits(proj, f"rounds/r{r_}/board.html")) for r_ in (0, 1, 2)}
    assert all(h == p_ for h, p_ in answers.values()), (why, answers)
    assert answers[2][0] is True and answers[1][0] is False                                  # the latest round is open, a middle one is not
    assert answers[0][0] is (why in ("G1s empty", "G1s missing")), (why, answers)          # r0 only on a state the guard fully understands


@pytest.mark.parametrize("args,needle", [
    (["--old", "", "--new", "x", "--count", "1"], "--old is empty"),
    (["--old", "a", "--new", "a", "--count", "1"], "the same text"),
    (["--old", "a", "--new", "b", "--count", "0"], "1 or more"),
    (["--old", "a", "--count", "1"], "one of each"),
])
def test_patch_usage_errors_are_exit_2(proj, args, needle):
    r = bc("patch", "book.html", *args, project=proj)
    assert r.returncode == 2 and needle in r.stderr


def test_an_approved_edition_is_not_edited_in_place(proj):
    assert bc("state", "--record", "G5", "approved", project=proj).returncode == 0
    assert state(proj).get("approved_edition") == "1"
    before = (proj / "book.html").read_bytes()
    r = bc("patch", "book.html", "--old", "alpha", "--new", "omega", "--count", "2", project=proj)
    assert r.returncode == 1 and "was approved" in r.stderr and "--new-edition" in r.stderr
    assert (proj / "book.html").read_bytes() == before
    r = bc("patch", "book.html", "--old", "alpha", "--new", "omega", "--count", "2", "--new-edition", project=proj)
    assert r.returncode == 0, r.stderr
    assert state(proj).get("edition") == "2" and state(proj).get("approved_edition") == "1"     # edition 2 is not approved by edition 1's G5
    assert log(proj) == ["- 2026-10-17 edition 2: opened (edition 1 stays as approved)", "- 2026-10-17 edition 2: patched book.html (2 replacements)"]


def test_recording_g5_writes_the_approved_edition_and_set_validates_it(proj):
    assert bc("state", "--set", "edition=3", project=proj).returncode == 0
    assert bc("state", "--record", "G5", "ok", project=proj).returncode == 0
    assert state(proj).get("approved_edition") == "3"
    r = bc("state", "--set", "edition=0", project=proj)
    assert r.returncode == 2 and "whole number" in r.stderr


def test_a_generated_book_is_never_patched_but_its_chapter_files_are(proj):
    assert bc("state", "--set", "mark_source=generated", project=proj).returncode == 0
    r = bc("patch", "book.html", "--old", "alpha", "--new", "omega", "--count", "2", project=proj)
    assert r.returncode == 1 and "is generated" in r.stderr and "book/chapters" in r.stderr
    (proj / "book/chapters").mkdir(parents=True)
    (proj / "book/chapters/idea.md").write_text("alpha alpha\n")
    assert bc("patch", "book/chapters/idea.md", "--old", "alpha", "--new", "omega", "--count", "2", project=proj).returncode == 0
    assert len(log(proj)) == 1 and "book/chapters/idea.md" in log(proj)[0]


# ---------------------------------------------------------------- collapse

MD = """## The idea

Shared text.

::: switcher nav
Pick A or B.
:::

::: variant nav a
Option A text.
:::

::: variant nav b
Option B text.
:::

::: variant other x
Another group stays.
:::

Closing text.
"""


def prim_tokens(p):
    (p / "tokens").mkdir(exist_ok=True)
    doc = {"color": {"$type": "color",
                     "ink": {"$value": {"colorSpace": "srgb", "components": [0, 0, 0], "alpha": 1, "hex": "#000000"}},
                     "rival-a": {"$value": {"colorSpace": "srgb", "components": [0, 1, 0], "alpha": 1, "hex": "#00ff00"},
                                 "$extensions": {"brand-creator": {"variant": "nav:a"}}},
                     "rival-b": {"$value": {"colorSpace": "srgb", "components": [1, 0, 0], "alpha": 1, "hex": "#ff0000"},
                                 "$extensions": {"brand-creator": {"variant": "nav:b"}}}}}
    (p / "tokens/primitives.tokens.json").write_text(json.dumps(doc, indent=2) + "\n")


@pytest.fixture
def open_choice(tmp_path):
    p = make_project(tmp_path, tier="standard")
    assert bc("state", "--set", "content_languages=en", project=p).returncode == 0
    (p / "book/chapters").mkdir(parents=True)
    (p / "book/chapters/idea.md").write_text(MD)
    prim_tokens(p)
    return p


def test_collapse_lists_what_is_open_and_the_dry_run_writes_nothing(open_choice):
    p = open_choice
    r = bc("collapse", "--list", project=p)
    assert r.returncode == 0
    assert "nav: a  (book/chapters/idea.md, tokens/primitives.tokens.json)" in r.stdout and "nav: (switcher)  (book/chapters/idea.md)" in r.stdout
    assert "other: x" in r.stdout
    before = {f: f.read_bytes() for f in (p / "book/chapters/idea.md", p / "tokens/primitives.tokens.json", p / "BRAND-STATE.md")}
    r = bc("collapse", "--group", "nav", "--keep", "a", project=p)
    assert r.returncode == 0 and "would change" in r.stdout and "nothing was written" in r.stdout
    assert {f: f.read_bytes() for f in before} == before and not list(p.glob("removed-*"))


def test_collapse_keeps_the_winner_drops_the_rest_backs_up_and_records(open_choice):
    p = open_choice
    original = (p / "book/chapters/idea.md").read_bytes()
    orig_tokens = (p / "tokens/primitives.tokens.json").read_bytes()
    r = bc("collapse", "--group", "nav", "--keep", "a", "--apply", project=p)
    assert r.returncode == 0, r.stderr
    md = (p / "book/chapters/idea.md").read_text()
    assert md.count("Option A text.") == 1 and "Option B text." not in md and "Pick A or B." not in md
    assert ":::" in md and "::: variant other x" in md and "Another group stays." in md        # another group is untouched
    assert "variant nav" not in md and "switcher nav" not in md and "Shared text." in md and "Closing text." in md
    doc = json.loads((p / "tokens/primitives.tokens.json").read_text())["color"]
    assert "rival-b" not in doc and "$extensions" not in doc["rival-a"] and "ink" in doc
    backup = p / "removed-2026-10-17"
    assert (backup / "book/chapters/idea.md").read_bytes() == original and (backup / "tokens/primitives.tokens.json").read_bytes() == orig_tokens
    text = (p / "BRAND-STATE.md").read_text()
    assert re.search(r"## Collapsed\n.*\n- 2026-10-17: nav decided, kept a; removed 1 variant block\(s\), 1 switcher\(s\) and 1 token\(s\)", text, re.S)
    assert "copies in removed-2026-10-17/" in text
    assert bc("collapse", "--list", project=p).stdout.count("nav:") == 0
    again = bc("collapse", "--group", "nav", "--keep", "a", "--apply", project=p)
    assert again.returncode == 2 and "no choice named 'nav'" in again.stderr      # nothing left to collapse


def test_collapse_with_an_unknown_keep_changes_nothing(open_choice):
    p = open_choice
    before = (p / "book/chapters/idea.md").read_bytes()
    r = bc("collapse", "--group", "nav", "--keep", "zzz", "--apply", project=p)
    assert r.returncode == 2 and "not an option of 'nav' (options: a, b)" in r.stderr
    assert (p / "book/chapters/idea.md").read_bytes() == before and not list(p.glob("removed-*"))


def test_collapse_second_backup_gets_its_own_folder(open_choice):
    p = open_choice
    (p / "removed-2026-10-17").mkdir()
    assert bc("collapse", "--group", "nav", "--keep", "b", "--apply", project=p).returncode == 0
    assert (p / "removed-2026-10-17-2/book/chapters/idea.md").is_file() and not (p / "removed-2026-10-17/book").exists()


def test_collapse_edits_a_hand_authored_book_and_refuses_an_approved_edition(open_choice):
    p = open_choice
    assert bc("state", "--set", "mark_source=authored-vector", project=p).returncode == 0
    page = ('<main>\n<div data-switcher="nav"><button>A</button><button>B</button></div>\n<section data-variant="nav:a"><p>A</p></section>\n'
            '<section data-variant="nav:b"><div><p>B</p></div></section>\n<p>after</p>\n</main>\n')
    (p / "book.html").write_text(page)
    assert bc("state", "--set", "edition=1", project=p).returncode == 0
    assert bc("state", "--record", "G5", "approved", project=p).returncode == 0
    r = bc("collapse", "--group", "nav", "--keep", "a", "--apply", project=p)
    assert r.returncode == 1 and "--new-edition" in r.stderr and (p / "book.html").read_text() == page
    r = bc("collapse", "--group", "nav", "--keep", "a", "--apply", "--new-edition", project=p)
    assert r.returncode == 0, r.stderr
    out = (p / "book.html").read_text()
    assert out == '<main>\n<section><p>A</p></section>\n<p>after</p>\n</main>\n'
    assert (p / "removed-2026-10-17/book.html").read_text() == page
    assert state(p).get("edition") == "2"
    assert "edition 2: collapsed nav to a" in (p / "BRAND-STATE.md").read_text()
