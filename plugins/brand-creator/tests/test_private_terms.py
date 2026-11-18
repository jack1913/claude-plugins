"""tests/tools/private_terms.py: the scan that keeps private terms out of a push. It is the tool of whoever holds private brand projects, run on
their own machine; these tests run it on made-up brands, in git repositories they make themselves. Nothing private is stored here."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import ROOT

sys.path.insert(0, str(ROOT / "tests" / "tools"))
import private_terms  # noqa: E402

TOOL = ROOT / "tests" / "tools" / "private_terms.py"
STATE = "---\nslug: {slug}\nname: \"{name}\"\ntier: quick\n---\n\n# {name}\n"


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=nobody", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
                       cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout.strip()


def commit(repo: Path, message: str, **files: str) -> str:
    for name, text in files.items():
        f = repo / name.replace("__", "/")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return git(repo, "rev-parse", "--short", "HEAD")


def tool(repo: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=repo, capture_output=True, text=True, input=stdin)


@pytest.fixture
def world(tmp_path):
    """A folder of two made-up brand projects, one private and one public, and a repository with one clean commit."""
    brands = tmp_path / "brands"
    for slug, name in (("zolta-laka", "Żółta Łąka"), ("opencorp", "Opencorp")):
        (brands / slug).mkdir(parents=True)
        (brands / slug / "BRAND-STATE.md").write_text(STATE.format(slug=slug, name=name), encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    commit(repo, "start", **{"README.md": "Acme is a made-up brand. Opencorp is public.\n"})
    return brands, repo


def test_a_brand_projects_name_and_slug_are_the_terms_and_a_public_project_is_left_out(world):
    brands, _ = world
    terms, seen = private_terms.project_terms(brands, {"opencorp"})
    assert sorted(terms) == ["zolta-laka", "Żółta Łąka"] and seen == {"opencorp", "zolta-laka"}
    loaded = private_terms.load([str(brands)], ["opencorp"], [])
    assert loaded.terms == ["zolta laka", "zolta-laka"]                                     # folded: no accents, lower case
    assert loaded.in_line("We made ŻÓŁTA  łąka last year.") == ["'zolta laka'"]             # however it is spelt
    assert loaded.in_line("Opencorp is public.") == [] and loaded.in_path("brands/zolta-laka/logo.svg") == ["'zolta-laka'"]


def test_a_list_adds_terms_and_colours_and_an_allowed_phrase_holds_a_term_without_a_hit(tmp_path):
    f = tmp_path / "more.json"
    f.write_text(json.dumps({"terms": ["Zorblax"], "hex": ["#123ABC"], "allow": ["zorblaxes"]}), encoding="utf-8")
    terms = private_terms.load([], [], [str(f)])
    assert terms.in_line("for Zorblax Industries") == ["'zorblax'"] and terms.in_line("two zorblaxes") == []
    assert terms.in_line("zorblaxes, then Zorblax") == ["'zorblax'"]                        # the phrase covers only its own place in the line
    for colour in ("#123abc", "#123ABCff", "color:%23123abc", "rgb(18, 58, 188)"):
        assert terms.in_line(colour) == ["the colour #123abc"], colour
    assert terms.in_line("#12abc0") == []


def test_a_range_is_scanned_by_what_it_adds_lines_paths_and_messages_and_a_term_removed_later_is_still_found(world):
    brands, repo = world
    src = ["--projects", str(brands), "--public", "opencorp"]
    base = git(repo, "rev-parse", "HEAD")
    assert tool(repo, *src, "--range", f"{base}..HEAD").returncode == 0                     # nothing added: nothing found
    a = commit(repo, "add a page", **{"docs__page.md": "one\ntwo\nThe client is Żółta Łąka.\n"})
    b = commit(repo, "take the name out", **{"docs__page.md": "one\ntwo\nThe client is Acme.\n"})
    c = commit(repo, "notes for zolta-laka")
    d = commit(repo, "an asset", **{"assets__zolta-laka.txt": "x\n", "docs__diff.txt": "++ not a file header: Zolta Laka\n"})
    r = tool(repo, *src, "--range", f"{base}..HEAD")
    assert r.returncode == 1 and not r.stdout, r.stderr
    assert f"{a} docs/page.md:3: 'zolta laka'" in r.stderr                                  # found in the commit that added it, though the tip is clean
    assert f"{b} " not in r.stderr                                                          # the commit that only takes it out adds nothing private
    assert f"{c} its message: 'zolta-laka'" in r.stderr
    assert f"{d} assets/zolta-laka.txt: the path holds 'zolta-laka'" in r.stderr
    assert f"{d} docs/diff.txt:1: 'zolta laka'" in r.stderr                                 # an added line that starts like a diff header is still a line
    assert "nothing was sent" in r.stderr and "opencorp" not in r.stderr.lower()
    assert tool(repo, *src, "--files").returncode == 1                                      # the files as they are: the asset's path is still there
    assert tool(repo, *src, "--range", f"{b}..{c}").returncode == 1 and tool(repo, *src, "--range", f"{a}..{b}").returncode == 0


def test_the_installed_hook_stops_a_push_with_a_private_term_and_lets_a_clean_one_through_on_a_new_branch_too(world, tmp_path):
    brands, repo = world
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    r = tool(repo, "install-hook", "--projects", str(brands), "--public", "opencorp")
    assert r.returncode == 0 and "every push from this clone is scanned for 2 term(s)" in r.stdout, r.stderr
    hook = repo / ".git" / "hooks" / "pre-push"
    assert hook.is_file() and (repo / ".git" / "hooks" / "private_terms.py").read_bytes() == TOOL.read_bytes()   # its own copy: a branch without the tool is scanned too
    push = ["git", "-c", "user.name=t", "-c", "user.email=nobody", "push", "-q", "origin"]
    assert subprocess.run([*push, "main"], cwd=repo, capture_output=True, text=True).returncode == 0            # a clean first push of a new branch
    commit(repo, "a leak", **{"notes.md": "for Zolta Laka\n"})
    r = subprocess.run([*push, "main"], cwd=repo, capture_output=True, text=True)
    assert r.returncode != 0 and "notes.md:1: 'zolta laka'" in r.stderr and "nothing was sent" in r.stderr, r.stderr
    assert git(remote, "rev-parse", "main") != git(repo, "rev-parse", "main")                                    # the remote did not get it
    git(repo, "switch", "-q", "-c", "side")                                                                      # a new branch carries the unpushed leak
    r = subprocess.run([*push, "side"], cwd=repo, capture_output=True, text=True)
    assert r.returncode != 0 and "notes.md:1: 'zolta laka'" in r.stderr, r.stderr
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    commit(repo, "clean notes", **{"notes.md": "for Acme\n"})
    assert subprocess.run([*push, "side"], cwd=repo, capture_output=True, text=True).returncode == 0
    assert tool(repo, "install-hook", "--projects", str(brands)).returncode == 0                                 # its own hook is written again


def test_a_hook_someone_else_wrote_is_never_replaced(world):
    brands, repo = world
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 0\n")
    r = tool(repo, "install-hook", "--projects", str(brands))
    assert r.returncode == 2 and "was not written by this tool" in r.stderr and hook.read_text() == "#!/bin/sh\nexit 0\n"


@pytest.mark.parametrize("args, why", [
    (["--files"], "no source"),
    (["--projects", "{empty}", "--files"], "no brand project there"),
    (["--projects", "{missing}", "--files"], "no such folder"),
    (["--projects", "{brands}", "--public", "nobody", "--files"], "no brand project with that slug"),
    (["--list", "{bad}", "--files"], "--list"),
    (["--list", "{none}", "--files"], "nothing to look for"),
    (["--projects", "{brands}"], "private_terms.py"),
    (["--projects", "{brands}", "--files", "--range", "HEAD"], "private_terms.py"),
    (["--projects", "{brands}", "--range", "no-such-revision..HEAD"], "git log"),
    (["install-hook"], "no source"),
])
def test_a_scan_that_cannot_run_says_why_and_exits_2_never_0(world, tmp_path, args, why):
    brands, repo = world
    (tmp_path / "empty").mkdir()
    (tmp_path / "bad.json").write_text("{not json")
    (tmp_path / "none.json").write_text('{"terms": [" "], "hex": []}')
    paths = {"brands": brands, "empty": tmp_path / "empty", "missing": tmp_path / "missing", "bad": tmp_path / "bad.json", "none": tmp_path / "none.json"}
    r = tool(repo, *[a.format(**paths) for a in args])
    assert r.returncode == 2 and "cannot scan" in r.stderr and why in r.stderr, (r.returncode, r.stderr)


def test_a_push_line_git_did_not_write_is_refused_and_a_deleted_ref_adds_nothing():
    zero = "0" * 40
    assert private_terms.pushed("origin", [f"(delete) {zero} refs/heads/old {'a' * 40}"]) == []
    assert private_terms.pushed("origin", [f"refs/heads/x {'b' * 40} refs/heads/x {zero}"]) == [["b" * 40, "--not", "--remotes=origin"]]
    assert private_terms.pushed("origin", [f"refs/heads/x {'b' * 40} refs/heads/x {'a' * 40}"]) == [[f"{'a' * 40}..{'b' * 40}"]]
    with pytest.raises(private_terms.CannotScan, match="not a line git gives"):
        private_terms.pushed("origin", ["refs/heads/x"])
