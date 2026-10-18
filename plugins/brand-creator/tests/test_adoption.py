"""adoption: the survey of product repositories (read only, ripgrep), rows as data with progress and pins, kept-not-counted, counts in sentences.

The target is tests/fixtures/target-repo, a synthetic repository. Expected values are worked out by hand from its files (line numbers counted in the
fixture) or recomputed by a plain Python walk of the fixture, never taken from the survey's own output. Mutation tests break a scratch copy and assert
that the mutation applied and the gate now fails."""
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import pytest
from helpers import ROOT, bc, make_project, mutate, mutate_json

import adoptdata as ad

pytestmark = pytest.mark.requires_rg
FIX = ROOT / "tests" / "fixtures" / "target-repo"
NAMES = ["--old-name", "Oldco", "--old-name", "Old Co"]
COLOURS = ["--old-colour", "#123456", "--old-colour", "#0a0a0a"]


def tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture
def repo(tmp_path) -> Path:
    r = tmp_path / "shop"
    shutil.copytree(FIX, r)
    (r / "ignored").mkdir()
    (r / "ignored" / "n.txt").write_text("Oldco ignored by .gitignore\n")   # created here: a fixture's own .gitignore would hide it from git
    return r


@pytest.fixture
def proj(tmp_path):
    return make_project(tmp_path, tier="full")


def survey(proj, repo, *extra, label="shop"):
    return bc("adoption", "survey", "--repo", f"{repo}={label}", *NAMES, *COLOURS, *extra, project=proj)


def load(proj) -> dict:
    return json.loads((proj / "adoption.json").read_text())


def rows_of(doc, category):
    return [r for r in doc["rows"] if r["category"] == category]


def hand_count(root: Path, pattern: str) -> dict:
    """File -> matching line numbers, by a plain Python walk that honours the fixture's .gitignore (ignored/) and nothing else."""
    rx = re.compile(pattern, re.I)
    out = {}
    for p in sorted(root.rglob("*")):
        rp = p.relative_to(root).as_posix()
        if not p.is_file() or rp.startswith((".git/", "ignored/")) or rp == ".gitignore" or p.suffix in (".png", ".ico"):
            continue
        hits = [i for i, ln in enumerate(p.read_text(errors="replace").splitlines(), 1) if rx.search(ln)]
        if hits:
            out[rp] = hits
    return out


# ---------------------------------------------------------------- the survey finds the slots

def test_survey_finds_names_colours_icons_metadata_and_badges_with_the_lines_counted_by_hand(proj, repo):
    r = survey(proj, repo)
    assert r.returncode == 0, r.stdout + r.stderr
    doc = load(proj)
    names = {x["file"]: x["lines"] for x in rows_of(doc, "name")}
    # lines counted by hand in tests/fixtures/target-repo; CHANGELOG.md, LICENSE, package-lock.json and dist/ are kept (below)
    assert names == {"README.md": [1, 4, 6], "app.metainfo.xml": [3, 4], "docs/notes.md": [3, 4], "macos/Info.plist": [5, 7],
                     "package.json": [2, 4, 6], "public/manifest.webmanifest": [2, 3], "src-tauri/tauri.conf.json": [2, 3], "src/main/app.rs": [2, 3, 4]}
    cols = {x["file"]: x["lines"] for x in rows_of(doc, "colour")}
    assert cols == {"README.md": [8], "public/manifest.webmanifest": [4], "src/theme.css": [2, 3, 4]}      # hex, rgb(18, 52, 86) and the upper-case hex
    assert {x["file"] for x in rows_of(doc, "path")} == {"assets/icons.appiconset", "docs/img", "public", "src-tauri/icons"}
    seen = {x["file"]: doc["seen"][str(x["n"])]["hits"] for x in rows_of(doc, "path")}
    assert seen == {"assets/icons.appiconset": 3, "docs/img": 1, "public": 1, "src-tauri/icons": 1}
    assert {x["file"] for x in rows_of(doc, "meta")} == {"app.metainfo.xml", "macos/Info.plist", "package.json", "public/manifest.webmanifest", "src-tauri/tauri.conf.json"}
    assert {x["file"]: x["lines"] for x in rows_of(doc, "badge")} == {"README.md": [3, 4]}
    # nothing from the ignored folder anywhere, and the numbers run 1..N in order
    assert "ignored/n.txt" not in json.dumps(doc)
    assert [x["n"] for x in doc["rows"]] == list(range(1, len(doc["rows"]) + 1)) and doc["nrows"] == len(doc["rows"])


def test_every_match_is_a_row_or_kept_and_the_totals_agree_with_a_plain_walk(proj, repo):
    assert survey(proj, repo).returncode == 0
    doc = load(proj)
    walk = hand_count(repo, r"oldco|old-co|old_co|old co")
    got = {}
    for x in doc["rows"]:
        if x["category"] == "name":
            got[x["file"]] = x["lines"]
    for k in doc["kept"]:
        if k["category"] == "name":
            got[k["file"]] = k["lines"]
    assert got == walk                                           # the oracle is the walk, not the survey
    kept = {k["file"]: k["reason"] for k in doc["kept"]}
    assert set(kept) == {"CHANGELOG.md", "LICENSE", "dist/bundle.js", "package-lock.json"}
    assert "history" in kept["CHANGELOG.md"] and "legal" in kept["LICENSE"] and "generated" in kept["dist/bundle.js"] and "lock file" in kept["package-lock.json"]
    acc = doc["accounting"]
    assert acc["hits"] == acc["in_rows"] + acc["kept"] and acc["kept"] == 4
    md = (proj / "ADOPTION.md").read_text()
    assert "## Kept, not counted" in md
    for f in kept:
        assert f"`{f}`" in md

def test_the_accounting_row_recounts_names_and_colours_with_a_second_ripgrep_run(proj, repo):
    assert survey(proj, repo).returncode == 0
    acc = next(x for x in json.loads((proj / "assets" / "_checks" / "adoption.json").read_text())["results"] if x["id"] == "accounting")
    n_names = sum(len(v) for v in hand_count(repo, r"oldco|old-co|old_co|old co").values())
    n_cols = sum(len(v) for v in hand_count(repo, r"(#|0x)(123456|0a0a0a)(?![0-9a-f])|rgba?\(\s*(18\s*,\s*52\s*,\s*86|10\s*,\s*10\s*,\s*10)\s*[,)]").values())
    assert acc["status"] == "pass" and n_names > 0 and n_cols > 0
    assert f"the {n_names} name and {n_cols} colour lines were counted again" in acc["detail"], acc["detail"]


def test_the_accounting_row_fails_when_the_second_count_disagrees(proj, repo, tmp_path):
    import stat
    import shutil as sh
    real = sh.which("rg")
    shim = tmp_path / "shim"
    shim.mkdir()
    f = shim / "rg"
    # a ripgrep that, in the per-file count mode only, reports one more matching line in a file that does not exist
    f.write_text(f'#!/bin/bash\n{real} "$@"\nrc=$?\ncase " $* " in *" --count "*) printf \'./planted.txt\\0001\\n\' ;; esac\nexit $rc\n')
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
    assert "--count" in f.read_text()
    r = bc("adoption", "survey", "--repo", f"{repo}=shop", *NAMES, *COLOURS, project=proj, env={"PATH": f"{shim}:{os.environ['PATH']}"})
    assert r.returncode == 1, r.stdout + r.stderr
    acc = next(x for x in json.loads((proj / "assets" / "_checks" / "adoption.json").read_text())["results"] if x["id"] == "accounting")
    assert acc["status"] == "fail" and "a second ripgrep count finds" in acc["detail"], acc["detail"]



def test_a_longer_hex_run_is_not_the_colour_and_every_way_of_writing_it_is(proj, repo):
    css = repo / "src" / "theme.css"
    mutate(css, ".logo {", "/* #1234567 and #12345678 are other colours */\n.short { color: #FFF; }\n.logo {")
    assert survey(proj, repo).returncode == 0
    cols = {x["file"]: x["lines"] for x in rows_of(load(proj), "colour")}
    assert cols["src/theme.css"] == [2, 3, 4]                    # the new line 6 holds longer hex runs and is not a match


def test_the_name_is_found_in_its_hyphen_underscore_and_any_case_forms(proj, repo):
    assert survey(proj, repo).returncode == 0
    notes = next(x for x in rows_of(load(proj), "name") if x["file"] == "docs/notes.md")
    assert notes["lines"] == [3, 4]                              # `old_co` (line 3) and `OLDCO` (line 4)


def test_survey_never_edits_the_repository_and_proves_it(proj, repo):
    before = tree(repo)
    r = survey(proj, repo)
    assert r.returncode == 0 and "read-only:shop" in r.stdout
    assert tree(repo) == before
    rep = json.loads((proj / "assets" / "_checks" / "adoption.json").read_text())
    ro = next(x for x in rep["results"] if x["id"] == "read-only:shop")
    assert ro["status"] == "pass" and rep["status"] == "pass"
    assert not (repo / "ADOPTION.md").exists() and not (repo / "adoption.json").exists()


def test_the_project_inside_the_repository_is_not_surveyed_as_the_repository(tmp_path):
    r = tmp_path / "site"
    shutil.copytree(FIX, r)
    p = make_project(r / "docs" / "brand", tier="full")
    with (p / "FACTS.md").open("a") as f:
        f.write("\nThe old name was Oldco.\n")                  # a file of the project that would match if it were surveyed as the repository's
    assert bc("adoption", "survey", "--repo", str(r), *NAMES, project=p).returncode == 0
    assert bc("adoption", "survey", "--repo", str(r), *NAMES, project=p).returncode == 0     # the project's own files are not rows (a second run finds nothing new)
    doc = load(p)
    assert doc["rows"] and not [x for x in doc["rows"] if x["file"].startswith("docs/brand")]
    assert not [k for k in doc["kept"] if k["file"].startswith("docs/brand")]


def test_icon_rows_name_the_pack_files_of_the_same_names(proj, repo):
    (proj / "assets").mkdir()
    (proj / "assets" / "manifest.json").write_text(json.dumps({"artefacts": [{"path": "assets/web/favicon.ico"}, {"path": "assets/web/icon.png"}]}))
    assert survey(proj, repo).returncode == 0
    doc = load(proj)
    pub = next(x for x in rows_of(doc, "path") if x["file"] == "public")
    assert "assets/web/favicon.ico" in pub["change"]
    other = next(x for x in rows_of(doc, "path") if x["file"] == "docs/img")
    assert "No pack file has one of these names" in other["change"]


def test_identifiers_are_recorded_for_the_rename_list(proj, repo):
    assert survey(proj, repo).returncode == 0
    ids = {(i["file"], i["what"]): i["value"] for i in load(proj)["identifiers"]}
    assert ids[("package.json", "package name")] == "oldco-app"
    assert ids[("src-tauri/tauri.conf.json", "app identifier")] == "com.oldco.app"
    assert ids[("macos/Info.plist", "bundle identifier")] == "com.oldco.app"
    assert ids[("app.metainfo.xml", "AppStream id")] == "com.oldco.app"


def test_an_owner_keep_rule_moves_a_file_from_the_rows_to_the_kept_list_with_the_reason(proj, repo):
    assert survey(proj, repo, "--keep", "docs/*.md::the notes quote the old tool on purpose").returncode == 0
    doc = load(proj)
    assert "docs/notes.md" not in [x["file"] for x in rows_of(doc, "name")]
    k = next(x for x in doc["kept"] if x["file"] == "docs/notes.md")
    assert "the notes quote the old tool on purpose" in k["reason"] and k["hits"] == 2


# ---------------------------------------------------------------- the document: numbered rows, counts in sentences, line numbers may drift

def test_adoption_md_numbers_the_rows_states_the_counts_and_says_lines_may_drift(proj, repo):
    assert survey(proj, repo).returncode == 0
    doc = load(proj)
    md = (proj / "ADOPTION.md").read_text()
    n = len(doc["rows"])
    assert f"Status: **not started**. 0 of {n} rows done, 0 doing, {n} to do." in md
    assert "Line numbers may drift: find the place by its content" in md and "Lines (may drift)" in md
    table = [ln for ln in md.splitlines() if re.match(r"^\| \d+ \|", ln)]
    assert len(table) == n and [int(re.match(r"^\| (\d+) \|", ln).group(1)) for ln in table] == list(range(1, n + 1))
    # the file count in the sentence is the number of distinct files among the non-icon rows, counted here from the data
    files = len({(x["repo"], x["file"]) for x in doc["rows"] if x["category"] != "path"})
    assert f"in {files} files" in md
    for ln in table:
        assert "to do" in ln and ln.rstrip().endswith(ad.MARK)


def test_a_hand_edit_of_adoption_md_is_caught(proj, repo):
    assert survey(proj, repo).returncode == 0
    mutate(proj / "ADOPTION.md", "| 1 | to do |", "| 1 | done |")
    r = bc("adoption", "verify", project=proj)
    assert r.returncode == 1 and "edited by hand" in r.stderr
    assert bc("adoption", "render", project=proj).returncode == 0
    assert bc("adoption", "verify", project=proj).returncode == 0


# ---------------------------------------------------------------- append-only: progress and pins

def test_a_second_survey_only_adds_rows_at_the_end_and_changes_nothing_else(proj, repo):
    assert survey(proj, repo).returncode == 0
    bc("state", "--record", "G6", "go (test)", project=proj)
    assert bc("adoption", "status", "--set", "1-3=done", project=proj).returncode == 0
    before = load(proj)
    (repo / "docs" / "another.md").write_text("Oldco again\n")
    (repo / "src" / "theme.css").write_text((repo / "src" / "theme.css").read_text().replace(":root {", "\n\n:root {"))   # lines drift
    assert survey(proj, repo).returncode == 0
    after = load(proj)
    n0 = len(before["rows"])
    assert after["rows"][:n0] == before["rows"]                                    # no row is changed, moved or removed
    assert len(after["rows"]) == n0 + 1 and after["rows"][-1]["file"] == "docs/another.md" and after["rows"][-1]["n"] == n0 + 1
    assert after["progress"] == before["progress"] == {"1": "done", "2": "done", "3": "done"}
    assert after["pins"][str(n0 + 1)] == "r1|name|docs/another.md" and all(after["pins"][k] == v for k, v in before["pins"].items())
    css = next(x for x in after["rows"] if x["file"] == "src/theme.css" and x["category"] == "colour")
    assert after["seen"][str(css["n"])]["lines"] == [4, 5, 6] and css["lines"] == [2, 3, 4]   # the live lines drift, the row text does not
    assert bc("adoption", "verify", project=proj).returncode == 0


def test_a_survey_with_nothing_new_is_byte_identical(proj, repo):
    assert survey(proj, repo).returncode == 0
    a1, m1 = (proj / "adoption.json").read_bytes(), (proj / "ADOPTION.md").read_bytes()
    assert bc("adoption", "survey", project=proj).returncode == 0                  # no --repo: the stored repositories, the stored terms
    assert (proj / "adoption.json").read_bytes() == a1 and (proj / "ADOPTION.md").read_bytes() == m1


def test_a_row_that_matches_nothing_any_more_stays_and_says_so(proj, repo):
    assert survey(proj, repo).returncode == 0
    n = next(x["n"] for x in load(proj)["rows"] if x["file"] == "src/main/app.rs" and x["category"] == "name")
    mutate(repo / "src" / "main" / "app.rs", "Oldco", "Newco")
    mutate(repo / "src" / "main" / "app.rs", "oldco_version", "newco_version", 2)
    assert bc("adoption", "survey", project=proj).returncode == 0
    doc = load(proj)
    assert doc["seen"][str(n)]["hits"] == 0 and any(x["n"] == n for x in doc["rows"])
    assert "match nothing at the last survey" in (proj / "ADOPTION.md").read_text()


@pytest.mark.parametrize("how", ["insert", "delete", "swap", "edit"])
def test_pins_make_an_inserted_removed_moved_or_edited_row_fail(proj, repo, how):
    assert survey(proj, repo).returncode == 0
    p = proj / "adoption.json"

    def change(d):
        rows = d["rows"]
        if how == "insert":
            rows.insert(2, {**rows[0], "n": 3, "file": "new/file.md"})
            for i, r in enumerate(rows, 1):
                r["n"] = i
        elif how == "delete":
            del rows[3]
            for i, r in enumerate(rows, 1):
                r["n"] = i
        elif how == "swap":
            rows[0], rows[1] = rows[1], rows[0]
            rows[0]["n"], rows[1]["n"] = 1, 2
        else:
            rows[4]["file"] = "somewhere/else.json"
    mutate_json(p, change)
    r = bc("adoption", "verify", project=proj)
    assert r.returncode == 1, r.stdout + r.stderr
    assert re.search(r"pinned|inserted, moved or edited|append-only", r.stderr)
    assert bc("check", project=proj).returncode == 1                               # check gates the same
    rep = json.loads((proj / "assets" / "_checks" / "check.json").read_text())
    assert next(x for x in rep["results"] if x["id"] == "adoption:data")["status"] == "fail"
    assert bc("adoption", "status", "--set", "1=to do", project=proj).returncode == 1   # and nothing builds on it


def test_progress_for_a_row_that_does_not_exist_fails(proj, repo):
    assert survey(proj, repo).returncode == 0
    mutate_json(proj / "adoption.json", lambda d: d["progress"].update({"999": "done"}))
    r = bc("adoption", "verify", project=proj)
    assert r.returncode == 1 and "row 999" in r.stderr


def test_status_needs_g6_for_doing_and_done_and_a_reversal_is_one_step(proj, repo):
    assert survey(proj, repo).returncode == 0
    r = bc("adoption", "status", "--set", "1=doing", project=proj)
    assert r.returncode == 1 and "G6" in r.stderr and load(proj)["progress"] == {}
    assert bc("adoption", "status", "--set", "1=to do", project=proj).returncode == 0           # to do needs no gate (it only reverses)
    bc("state", "--record", "G6", "go (test)", project=proj)
    r = bc("adoption", "status", "--set", "1,3-4=doing", "--set", "2=done", project=proj)
    assert r.returncode == 0, r.stderr
    assert load(proj)["progress"] == {"1": "doing", "2": "done", "3": "doing", "4": "doing"}
    n = len(load(proj)["rows"])
    md = (proj / "ADOPTION.md").read_text()
    assert f"Status: **in progress**. 1 of {n} rows done, 3 doing, {n - 4} to do." in md
    assert bc("adoption", "status", "--set", "1=to do", project=proj).returncode == 0
    assert "1" not in load(proj)["progress"]
    out = bc("adoption", "status", "--json", project=proj).stdout
    assert json.loads(out)["counts"] == {"to do": n - 3, "doing": 2, "done": 1}


@pytest.mark.parametrize("args,needle", [
    (["--set", "99=done"], "rows 1 to"), (["--set", "1=finished"], "STATE one of"), (["--set", "abc=done"], "use N, N-M"), (["--set", "3-1=done"], "rows '3-1'")])
def test_status_rejects_bad_input(proj, repo, args, needle):
    assert survey(proj, repo).returncode == 0
    bc("state", "--record", "G6", "go (test)", project=proj)
    r = bc("adoption", "status", *args, project=proj)
    assert r.returncode == 2 and needle in r.stderr


def test_a_done_row_that_still_matches_is_flagged(proj, repo):
    assert survey(proj, repo).returncode == 0
    bc("state", "--record", "G6", "go (test)", project=proj)
    assert bc("adoption", "status", "--set", "1=done", project=proj).returncode == 0
    r = bc("check", project=proj)
    rep = json.loads((proj / "assets" / "_checks" / "check.json").read_text())
    assert next(x for x in rep["results"] if x["id"] == "adoption:drift")["status"] == "warn"
    assert next(x for x in rep["results"] if x["id"] == "adoption:data")["status"] == "pass"


# ---------------------------------------------------------------- usage errors

@pytest.mark.parametrize("args,needle", [
    (["--old-name", "ab"], "shorter than 3"), (["--old-colour", "teal"], "not a hex colour"), (["--keep", "no-reason"], "GLOB::REASON"),
    (["--old-colours-file", "/nonexistent/colours.txt"], "not a file")])
def test_survey_rejects_bad_terms(proj, repo, args, needle):
    r = bc("adoption", "survey", "--repo", str(repo), *args, project=proj)
    assert r.returncode == 2 and needle in r.stderr and not (proj / "adoption.json").exists()


def test_survey_needs_a_repository_and_refuses_the_project_itself(proj, repo, tmp_path):
    r = bc("adoption", "survey", *NAMES, project=proj)
    assert r.returncode == 2 and "no repository" in r.stderr
    assert bc("adoption", "survey", "--repo", str(tmp_path / "missing"), project=proj).returncode == 2
    r = bc("adoption", "survey", "--repo", str(proj), project=proj)
    assert r.returncode == 2 and "brand project itself" in r.stderr
    assert bc("adoption", "status", project=proj).returncode == 2        # no survey yet


def test_a_colours_file_is_read_and_comments_are_skipped(proj, repo, tmp_path):
    f = tmp_path / "old.txt"
    f.write_text("// the old palette\n#123456\n")
    r = bc("adoption", "survey", "--repo", f"{repo}=shop", "--old-colours-file", str(f), project=proj)
    assert r.returncode == 0, r.stderr
    doc = load(proj)
    assert doc["terms"]["colours"] == ["#123456"] and {x["file"] for x in rows_of(doc, "colour")} == {"README.md", "public/manifest.webmanifest", "src/theme.css"}


def test_without_terms_only_the_structural_slots_are_surveyed_and_the_warning_says_so(proj, repo):
    r = bc("adoption", "survey", "--repo", str(repo), project=proj)
    assert r.returncode == 0 and "WARN" in r.stdout and "none given" in r.stdout
    doc = load(proj)
    assert not rows_of(doc, "name") and not rows_of(doc, "colour") and rows_of(doc, "path") and rows_of(doc, "meta")


def test_a_missing_ripgrep_is_exit_3_with_the_fix_and_writes_nothing(proj, repo, tmp_path):
    bin_ = tmp_path / "pathbin"
    bin_.mkdir()
    for tool in ("uv", "python3", "bash"):
        p = shutil.which(tool)
        assert p, tool
        (bin_ / tool).symlink_to(p)
    path = os.pathsep.join([str(bin_), "/usr/bin", "/bin"])
    assert shutil.which("rg", path=path) is None, "precondition: rg must be hidden, or this test proves nothing"
    r = bc("adoption", "survey", "--repo", str(repo), *NAMES, project=proj, env={"PATH": path})
    assert r.returncode == 3 and "ripgrep" in r.stderr and "Install" in r.stderr
    assert not (proj / "adoption.json").exists() and not (proj / "ADOPTION.md").exists()


# ---------------------------------------------------------------- hand-written rows

def test_a_code_change_no_search_finds_is_added_as_a_pinned_row_that_a_survey_leaves_alone(proj, repo):
    assert survey(proj, repo).returncode == 0
    n0 = len(load(proj)["rows"])
    r = bc("adoption", "add", "--repo", "shop", "--file", "src/main/app.rs", "--lines", "2-4", "--find", "fn main",
           "--change", "Show the tray state in words: the menu row is the only text about it on Linux.", project=proj)
    assert r.returncode == 0, r.stderr
    doc = load(proj)
    row = doc["rows"][-1]
    assert row["n"] == n0 + 1 and row["category"] == "change" and row["lines"] == [2, 3, 4] and doc["pins"][str(n0 + 1)] == "r1|change|src/main/app.rs"
    assert bc("adoption", "survey", project=proj).returncode == 0
    again = load(proj)
    assert again["rows"][-1] == row and str(n0 + 1) not in again["seen"]
    md = (proj / "ADOPTION.md").read_text()
    assert f"| {n0 + 1} | to do | Code change | shop | `src/main/app.rs` | 2-4 | `fn main` |" in md and "1 row(s) are code changes written by hand" in md
    assert "match nothing" not in md
    assert bc("adoption", "verify", project=proj).returncode == 0
    # a hand-written row is pinned like the others
    mutate_json(proj / "adoption.json", lambda d: d["rows"][-1].update({"file": "elsewhere.rs"}))
    assert bc("adoption", "verify", project=proj).returncode == 1


def test_adding_a_row_needs_a_surveyed_repository_and_all_the_words(proj, repo):
    assert survey(proj, repo).returncode == 0
    r = bc("adoption", "add", "--repo", "other", "--file", "a", "--find", "b", "--change", "c", project=proj)
    assert r.returncode == 2 and "not a surveyed repository" in r.stderr
    r = bc("adoption", "add", "--repo", "shop", "--file", "a", "--find", " ", "--change", "c", project=proj)
    assert r.returncode == 2 and "--find is empty" in r.stderr
    assert len(load(proj)["rows"]) == load(proj)["nrows"]


def test_adoption_md_is_rendered_through_the_template_frame_and_a_broken_frame_is_an_error(proj, repo, tmp_path, monkeypatch):
    """templates/ADOPTION.md holds the fixed text (the apply rules); the data parts stay in their order; a frame without a placeholder fails."""
    assert survey(proj, repo).returncode in (0, 1)
    md = (proj / "ADOPTION.md").read_text()
    heads = [ln for ln in md.splitlines() if ln.startswith("#")]
    assert heads[0].endswith(": adoption") and heads[1:] == ["## How this list is applied", "## Kept, not counted"], heads
    flat = " ".join(md.split())
    for rule in ("branch the owner names", "by the text in the Find column, never by the line number", "byte for byte", "(`cmp`)",
                 "hooks always run", "Commit, merge and push are three separate asks", "needs its own OK"):
        assert rule in flat, rule
    assert md.index("| # | Status |") < md.index("## How this list is applied") < md.index("## Kept, not counted")
    assert "{{" not in md and "\n\n\n" not in md
    from _common import CliError
    broken = tmp_path / "ADOPTION.md"
    broken.write_text(ad.TEMPLATE.read_text().replace("{{kept}}", ""))
    assert "{{kept}}" not in broken.read_text()                  # the mutation applied
    monkeypatch.setattr(ad, "TEMPLATE", broken)
    with pytest.raises(CliError, match=r"lacks the placeholders \['kept'\]"):
        ad.render(load(proj), "Acme")
