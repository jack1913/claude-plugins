"""Tests for `brand-creator cleanup` (scripts/cleanup.py, scripts/boardlib/rounds.py): old round folders out through git, after the owner's yes.

Every test builds a small project in tmp_path, with its own git repository. Every git call and every run sets HOME and XDG_CONFIG_HOME into tmp_path, so the developer's global ignore and
configuration play no part (the command drops every GIT_* variable itself, so the tests cannot rely on GIT_CONFIG_GLOBAL).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import BIN, ROOT, bc, path_without

sys.path.insert(0, str(ROOT / "scripts"))
import cleanup  # noqa: E402
import rounds as rounds_mod  # noqa: E402

DATE = "2026-11-05"
_UV = {k: subprocess.run(["uv", *cmd], capture_output=True, text=True).stdout.strip() for k, cmd in (("UV_CACHE_DIR", ["cache", "dir"]), ("UV_PYTHON_INSTALL_DIR", ["python", "dir"]))}

# ---- builders

BASE = {0: "style", 1: "pick", 2: "refine", 3: "refine", 4: "refine"}   # r0 style, r1 the latest pick board, r4 the latest mark board: r2 and r3 are candidates


def board(kind: str, n: int, *, stage: str | None = None, hero: str | None = None, body: str = "") -> str:
    attrs = f'data-round="{n}" data-board="{kind}"' + (f' data-site-stage="{stage}"' if stage else "") + (f' data-hero="{hero}"' if hero else "")
    return f"<!doctype html><html><body {attrs}>{body}</body></html>\n"


def board_for(spec: str, n: int, hero: str | None = None) -> str | None:
    if spec == "none":
        return None
    if spec == "plain":
        return "<!doctype html><html><body>no kind</body></html>\n"
    if spec == "copied":
        return board("pick", n + 100)
    if spec == "hero":
        return board("site", n, stage="hero", body=f'<div data-site-variant="v{n}"></div>')
    if spec == "pages":
        return board("site", n, stage="pages", hero=hero)
    return board(spec, n)


class Proj:
    def __init__(self, tmp_path: Path, *, sub: str = "", name: str = "repo"):
        self.tmp = tmp_path
        self.home = tmp_path / "home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.repo = tmp_path / name
        self.repo.mkdir(parents=True, exist_ok=True)
        self.dir = self.repo / sub if sub else self.repo
        self.dir.mkdir(parents=True, exist_ok=True)

    @property
    def env(self) -> dict:
        return {**_UV, "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"), "BRAND_CREATOR_TODAY": DATE}

    def git(self, *args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
        cp = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=nobody", "-c", "commit.gpgsign=false", *args], cwd=cwd or self.repo,
                            capture_output=True, text=True, env={**os.environ, "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config")})
        if check:
            assert cp.returncode == 0, cp.stderr
        return cp

    def write(self, rel: str, content: str | bytes = "x\n") -> Path:
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")
        return p

    def commit(self, msg: str = "c") -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)

    def run(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return bc("cleanup", *args, project=self.dir, env={**self.env, **(env or {})})

    def code(self, *keeps: str) -> str:
        r = self.run(*keeps)
        assert r.returncode == 0, r.stderr + r.stdout
        return re.search(r"code: ([0-9a-f]{12})", r.stdout).group(1)

    def yes(self, code: str, *keeps: str, said: str = "the owner agreed") -> subprocess.CompletedProcess:
        r = self.run(*keeps, "--record-yes", code, "--said", said)
        assert r.returncode == 0, r.stderr + r.stdout
        return self.run(*keeps, "--yes", code)

    def snapshot(self) -> dict[str, str]:
        out = {}
        for p in sorted(self.repo.rglob("*")):
            rel = p.relative_to(self.repo).as_posix()
            if rel == ".git" or rel.startswith(".git/") or not (p.is_file() or p.is_symlink()):
                continue
            out[rel] = "link:" + os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    def status(self) -> str:
        return self.git("status", "--porcelain=v2", "--untracked-files=all", "--ignored=matching", check=False).stdout


def make(tmp_path: Path, spec: dict[int, str] | None = None, *, git: bool = True, commit: bool = True, sub: str = "", name: str = "repo", state: str = "") -> Proj:
    p = Proj(tmp_path, sub=sub, name=name)
    p.write("BRAND-STATE.md", f"---\nslug: acme\ntier: standard\n{state}---\n\n# Acme\n")
    p.write("DECISIONS.md", "# Acme: decisions\n\nOne entry per decision.\n")
    for n, kind in (BASE if spec is None else spec).items():
        text = board_for(kind, n)
        if text is not None:
            p.write(f"rounds/r{n}/board.html", text)
        else:
            p.write(f"rounds/r{n}/notes.txt", "no board here\n")
        p.write(f"rounds/r{n}/mark.svg", f'<svg xmlns="http://www.w3.org/2000/svg" id="m{n}"/>\n')
    if git:
        p.git("init", "-q", "-b", "main")
        if commit:
            p.commit("start")
    return p


def parse_plan(out: str) -> tuple[set[int], set[int]]:
    kept, removed, cur = set(), set(), None
    for ln in out.splitlines():
        if ln.startswith("keep ("):
            cur = kept
        elif ln.startswith("remove ("):
            cur = removed
        elif ln.startswith("nothing to clean"):
            cur = kept
        elif ln.startswith("files to remove"):
            cur = None
        elif cur is not None and (m := re.match(r"^  r(\d+) ", ln)):
            cur.add(int(m.group(1)))
    return kept, removed


def reasons(out: str, n: int) -> str:
    m = re.search(rf"^  r{n} .*$", out.split("remove (")[0], re.M)
    return m.group(0) if m else ""


def refused_cleanly(p: Proj, r: subprocess.CompletedProcess, code: int, needle: str, before: dict[str, str], status: str) -> None:
    assert r.returncode == code, (r.stdout, r.stderr)
    assert needle in r.stderr + r.stdout, (needle, r.stderr, r.stdout)
    assert p.snapshot() == before, "a refusal must write nothing"
    assert p.status() == status
    assert not list((p.dir / "qa").glob("*cleanup*")) if (p.dir / "qa").exists() else True


# ---------------------------------------------------------------- plan and keep-set

def test_dry_run_is_the_default_and_removes_nothing(tmp_path):
    p = make(tmp_path)
    before, status = p.snapshot(), p.status()
    r = p.run()
    assert r.returncode == 0, r.stderr
    assert "brand-creator cleanup plan" in r.stdout and "remove (2 rounds" in r.stdout
    after = p.snapshot()
    assert {k: v for k, v in after.items() if k != f"qa/{DATE}-cleanup-plan.txt"} == before
    assert p.status().replace(f"? qa/{DATE}-cleanup-plan.txt\n", "") == status.replace(f"? qa/{DATE}-cleanup-plan.txt\n", "")
    assert not p.git("diff", "--cached", "--name-only").stdout and (p.dir / "rounds" / "r2" / "board.html").is_file()


def test_dry_run_writes_the_plan_file_and_prints_the_code(tmp_path):
    p = make(tmp_path)
    r = p.run()
    code = re.search(r"code: ([0-9a-f]{12})", r.stdout).group(1)
    plan = (p.dir / "qa" / f"{DATE}-cleanup-plan.txt").read_text(encoding="utf-8")
    assert plan == r.stdout.rsplit("plan file:", 1)[0]
    assert f"code: {code}" in plan and re.search(r"plan: sha256:[0-9a-f]{64}", plan) and f"--yes {code}" in plan
    assert "head: " + p.git("rev-parse", "HEAD").stdout.strip() in plan


def test_latest_round_of_each_stage_is_kept(tmp_path):
    spec = {0: "style", 1: "pick", 2: "refine", 3: "refine", 4: "refine", 5: "site-refs", 6: "hero", 7: "hero", 8: "hero", 9: "pages", 10: "pages", 11: "pages", 12: "motion", 13: "motion", 14: "motion"}
    p = make(tmp_path, spec)
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert kept == {0, 1, 4, 5, 6, 8, 9, 11, 12, 14} and removed == {2, 3, 7, 10, 13}, out
    assert "latest of its stage" in reasons(out, 8) and "latest pick board" in reasons(out, 1)
    assert "first site board of the hero stage" in reasons(out, 6) and "first motion board" in reasons(out, 12)


def test_the_latest_pick_board_is_kept_besides_the_latest_mark_board(tmp_path):
    kept, removed = parse_plan(make(tmp_path, {0: "style", 1: "pick", 2: "pick", 3: "refine", 4: "refine"}).run().stdout)
    assert kept == {0, 2, 4} and removed == {1, 3}


def test_the_highest_round_is_always_kept(tmp_path):
    for i, kind in enumerate(("style", "pick", "refine", "motion", "site-refs", "hero", "pages", "plain", "none")):
        p = make(tmp_path / f"p{i}", {0: "pick", 1: "refine", 2: "refine", 3: kind})
        r = p.run()
        assert r.returncode == 0 and 3 in parse_plan(r.stdout)[0], (kind, r.stdout)


def test_a_round_of_unknown_kind_is_kept(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "none", 4: "plain", 5: "copied", 6: "refine", 7: "refine"})
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert {3, 4, 5} <= kept and removed == {2, 6}, out
    assert "unknown" in reasons(out, 3) and "can place" in reasons(out, 3)


SOURCES = {
    "BRAND-STATE.md": ("BRAND-STATE.md", "---\nslug: acme\ntier: standard\n---\n\nThe mark is in rounds/r2/mark.svg.\n"),
    "DECISIONS.md": ("DECISIONS.md", "# d\n\n## 2026-10-01: a\n\n- Decided: rounds/r2/mark.svg\n"),
    "decisions-adr": ("decisions/ADR-0001-x.md", "# ADR\n\nSource: rounds/r2/board.html\n"),
    "FACTS.md": ("FACTS.md", "| mark | rounds/r2/mark.svg |\n"),
    "book.html": ("book.html", '<html><body><img src="rounds/r2/mark.svg" alt=""></body></html>\n'),
    "book-chapter": ("book/chapters/history.md", "See ![mark](../../rounds/r2/mark.svg).\n"),
    "applied-skill": (".claude/skills/x-brand/SKILL.md", "The master is rounds/r2/mark.svg.\n"),
    "tools-gen": ("tools/gen.py", "SRC = 'rounds/r2/mark.svg'\n"),
    "site-page": ("site/start/index.html", '<html><body><img src="../../rounds/r2/mark.svg" alt=""></body></html>\n'),
    "motion-json": ("motion/motion.json", '{"proof": "rounds/r2/proof.json"}\n'),
    "manifest": ("assets/manifest.json", '{"files": [{"path": "rounds/r2/mark.svg"}]}\n'),
    "tray": ("tray/tray.json", '{"states": [{"master": "rounds/r2/mark.svg"}]}\n'),
    "states": ("qa/states.json", '{"sets": [["rounds/r2/mark.svg"]]}\n'),
    "design": (".design/x/canvas.json", '{"image": "rounds/r2/mark.svg"}\n'),
    "research": ("research/notes.md", "The old mark rounds/r2/mark.svg was too soft.\n"),
    "webmanifest": ("assets/web/site.webmanifest", '{"icons": [{"src": "rounds/r2/m.png"}]}\n'),
    "cp1250-csv": ("tools/kit.csv", "name;file\nzażółć;rounds/r2/mark.svg\n".encode("cp1250")),
    "cascade-also": ("tools/cascade.json", '{"schema": 1, "also": ["../parent/README.md"]}\n'),
    "family-parent": ("FAMILY.md", '# Family\n\n```json family-check\n{"parent_docs": ["../parent/README.md"]}\n```\n'),
}


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_a_referenced_round_is_kept(tmp_path, source):
    p = make(tmp_path)
    path, content = SOURCES[source]
    if source in ("cascade-also", "family-parent"):
        (tmp_path / "parent").mkdir()
        (tmp_path / "parent" / "README.md").write_text("The parent brand uses rounds/r2/mark.svg.\n", encoding="utf-8")
    p.write(path, content)
    p.commit()
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert 2 in kept and 3 in removed, out
    assert "referenced:" in reasons(out, 2)


@pytest.mark.parametrize("name,path,text,keeps", [
    ("json-escaped-slash", "assets/x.json", '{"p": "rounds\\/r2\\/a.svg"}\n', True),
    ("json-double-backslash", "assets/x.json", '{"p": "rounds\\\\r2\\\\a.svg"}\n', True),
    ("percent-encoded", "site/start/index.html", '<a href="rounds%2Fr2%2Fa.svg">x</a>\n', True),
    ("upper-case-folder", "research/n.md", "ROUNDS/r2/a.svg\n", True),
    ("upper-case-round", "research/n.md", "rounds/R2/a.svg\n", True),
    ("backslash", "research/n.md", "rounds\\r2\\a.svg\n", True),
    ("no-separator", "research/n.md", "roundsr2 and rounds//r2\n", False),
])
def test_reference_spellings_are_read(tmp_path, name, path, text, keeps):
    p = make(tmp_path)
    p.write(path, text)
    p.commit()
    kept, removed = parse_plan(p.run().stdout)
    assert (2 in kept) is keeps and (2 in removed) is (not keeps), name


def test_a_relative_link_from_a_kept_round_keeps_its_target(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "refine", 4: "refine", 5: "refine"})
    p.write("rounds/r5/page.html", '<html><body><img src="../r2/mark.svg" alt=""></body></html>\n')
    p.write("rounds/r5/build.html", '<html><body><script>var u = "../r3/mark.svg";</script></body></html>\n')
    p.commit()
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert kept >= {2, 3} and removed == {4}, out
    assert "r5/page.html" in reasons(out, 2) and "r5/build.html" in reasons(out, 3)


def test_references_are_followed_to_a_fixed_point(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "refine", 4: "refine", 5: "refine"})
    p.write("rounds/r5/page.html", '<img src="../r4/mark.svg">\n')
    p.write("rounds/r4/page.html", '<img src="../r2/mark.svg">\n')
    p.commit()
    kept, removed = parse_plan(p.run().stdout)
    assert kept >= {2, 4, 5} and removed == {3}


def test_a_symbolic_link_in_a_source_into_a_round_keeps_it(tmp_path):
    p = make(tmp_path)
    (p.dir / "site").mkdir()
    os.symlink("../rounds/r2/mark.svg", p.dir / "site" / "link.svg")
    p.commit()
    out = p.run().stdout
    assert parse_plan(out)[0] >= {2} and "symbolic link" in reasons(out, 2)


def test_site_json_round_and_g1s_round_are_kept(tmp_path):
    p = make(tmp_path, state="g1s_round: 3\n")
    p.write("site/site.json", json.dumps({"schema": 1, "round": 2}) + "\n")
    p.commit()
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert kept >= {2, 3} and not removed, out
    assert "site/site.json round" in reasons(out, 2) and "g1s_round" in reasons(out, 3)


def test_a_project_without_site_json_cleans(tmp_path):
    p = make(tmp_path)
    assert not (p.dir / "site").exists()
    r = p.run()
    assert r.returncode == 0 and parse_plan(r.stdout)[1] == {2, 3}


@pytest.mark.parametrize("value", ['"3a"', "true", "-1"])
def test_a_site_json_round_that_is_not_a_whole_number_refuses(tmp_path, value):
    p = make(tmp_path)
    p.write("site/site.json", '{"schema": 1, "round": %s}\n' % value)
    p.commit()
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 1, "not a whole number", before, status)


def test_a_g1s_round_that_is_not_a_whole_number_refuses(tmp_path):
    p = make(tmp_path, state="g1s_round: 3a\n")
    p.commit()
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 1, "g1s_round", before, status)


def test_page_check_and_capture_inputs_of_a_kept_page_keep_their_round(tmp_path):
    p = make(tmp_path)
    p.write("site/start/index.html", "<html><body>x</body></html>\n")
    p.write("assets/_checks/page-check/site-start.json", json.dumps({"tool": "page-check/site-start", "run": {"target": {"kind": "project", "page": "site/start/index.html"}},
                                                                    "inputs": [{"path": "site/start/index.html", "sha256": "0" * 64}, {"path": "rounds/r2/mark.svg", "sha256": "0" * 64}]}))
    p.write("site/start/shots/capture.json", json.dumps({"tool": "capture", "source": {"page": "site/start/index.html"}, "inputs": [{"path": "rounds/r3/mark.svg", "sha256": "0" * 64}]}))
    p.commit()
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert kept >= {2, 3} and not removed, out
    assert "input of the report assets/_checks/page-check/site-start.json" in reasons(out, 2) and "capture.json" in reasons(out, 3)


def test_a_report_of_removed_work_pins_nothing_and_is_removed_with_its_round(tmp_path):
    p = make(tmp_path)
    rep = "assets/_checks/page-check/rounds-r2-index.json"
    p.write("rounds/r2/index.html", "<html><body>x</body></html>\n")
    p.write(rep, json.dumps({"tool": "page-check/x", "run": {"target": {"page": "rounds/r2/index.html"}}, "inputs": [{"path": "rounds/r3/mark.svg", "sha256": "0" * 64}]}))
    p.write("assets/_checks/contrast.json", json.dumps({"tool": "contrast", "inputs": []}))
    p.commit()
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert removed == {2, 3} and kept == {0, 1, 4}, out
    assert rep in out and "assets/_checks/contrast.json" not in out
    code = re.search(r"code: ([0-9a-f]{12})", out).group(1)
    assert p.yes(code).returncode == 0
    assert not (p.dir / rep).exists() and (p.dir / "assets/_checks/contrast.json").is_file()
    assert f"D  {p.dir.relative_to(p.repo).as_posix() + '/' if p.dir != p.repo else ''}{rep}" in p.git("status", "--porcelain").stdout


def test_a_report_of_a_kept_page_in_a_kept_round_keeps_its_inputs(tmp_path):
    p = make(tmp_path)
    p.write("assets/_checks/page-check/rounds-r4-index.json", json.dumps({"tool": "page-check/x", "run": {"target": {"page": "rounds/r4/index.html"}},
                                                                           "inputs": [{"path": "rounds/r2/mark.svg", "sha256": "0" * 64}]}))
    p.commit()
    kept, removed = parse_plan(p.run().stdout)
    assert kept >= {2} and removed == {3}


def test_history_removed_cleanup_records_and_canvas_briefs_are_not_sources(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "refine", 4: "refine", 5: "refine"})
    p.write("history/2026-10-01-approved/FROZEN.md", "# Kept as written\n\nfrozen from rounds/r2 on 2026-10-01\n")
    p.write("qa/2026-11-01-cleanup-plan.txt", "keep rounds/r3\n")
    p.write("qa/2026-11-01-cleanup-removed.txt", "removed rounds/r3\n")
    p.write("brief/canvas-round-4.md", "start from rounds/r4/mark.svg\n")
    p.write("removed-2026-10-01/page.html", "rounds/r3/mark.svg\n")
    p.commit()
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert removed == {2, 3, 4}, out
    assert "frozen in history/2026-10-01-approved/" in out


def test_keep_option_keeps_a_round_and_changes_the_code(tmp_path):
    p = make(tmp_path)
    plain = p.code()
    out = p.run("--keep", "r3").stdout
    kept, removed = parse_plan(out)
    assert kept >= {3} and removed == {2} and "kept with --keep" in reasons(out, 3)
    assert re.search(r"code: ([0-9a-f]{12})", out).group(1) != plain and "--keep r3 --yes" in out


def test_lint_context_keeps_the_first_motion_board(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "refine", 4: "motion", 5: "motion", 6: "motion"})
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert kept == {0, 1, 3, 4, 6} and removed == {2, 5}, out
    assert "first motion board" in reasons(out, 4)


def test_lint_context_keeps_the_first_board_of_a_site_stage(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "hero", 4: "hero", 5: "hero", 6: "pages", 7: "pages", 8: "pages"})
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert {3, 5, 6, 8} <= kept and removed == {4, 7}, out
    assert "first site board of the hero stage" in reasons(out, 3) and "first site board of the pages stage" in reasons(out, 6)


def test_lint_context_keeps_the_hero_board_data_hero_names(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine"})
    for n, name in ((3, "alpha"), (4, "beta"), (5, "gamma")):
        p.write(f"rounds/r{n}/board.html", board("site", n, stage="hero", body=f'<div data-site-variant="{name}"></div>'))
    p.write("rounds/r6/board.html", board("site", 6, stage="pages", hero="beta"))
    p.commit()
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert {3, 4, 5, 6} <= kept, out
    assert "hero board of the card r6 names" in reasons(out, 4)
    p2 = make(tmp_path / "other", {0: "style", 1: "pick", 2: "refine"})
    for n, name in ((3, "alpha"), (4, "beta"), (5, "gamma")):
        p2.write(f"rounds/r{n}/board.html", board("site", n, stage="hero", body=f'<div data-site-variant="{name}"></div>'))
    p2.write("rounds/r6/board.html", board("site", 6, stage="pages", hero="gamma"))
    p2.commit()
    assert 4 in parse_plan(p2.run().stdout)[1], "without data-hero naming it, the middle hero board goes"


def test_lint_context_keeps_the_rejected_round_of_a_reset_pick(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "style", 4: "pick"}, state="reset_rounds: [3, 4]\ng1s_round: 3\n")
    out = p.run().stdout
    kept, removed = parse_plan(out)
    assert kept == {2, 3, 4} and removed == {0, 1}, out
    assert "rejected round" in reasons(out, 2) and "style board of the reset" in reasons(out, 3)


def test_lint_context_check_refuses_when_a_rule_is_missing(tmp_path, monkeypatch, capsys):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "refine", 4: "motion", 5: "motion", 6: "motion"})
    for k, v in p.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(rounds_mod, "lint_context_keeps", lambda *a, **k: [])
    before, status = p.snapshot(), p.status()
    rc = cleanup.run_cli(["--project", str(p.dir)])
    err = capsys.readouterr().err
    assert rc == 1 and "would change how board-lint reads rounds/r6/board.html" in err and "bug in cleanup's keep rules" in err
    assert p.snapshot() == before and p.status() == status


def test_board_lint_verdicts_of_kept_boards_do_not_change(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "refine", 4: "motion", 5: "motion", 6: "motion"})

    def verdicts() -> dict:
        out = {}
        for n in (4, 6):
            r = bc("board-lint", f"rounds/r{n}/board.html", project=p.dir, env=p.env)
            assert r.returncode in (0, 1), r.stderr
            doc = json.loads((p.dir / "assets/_checks/board-lint.json").read_text(encoding="utf-8"))
            out[n] = [(x["id"], x["status"]) for x in doc["results"]]
        return out
    before = verdicts()
    shutil.rmtree(p.dir / "assets")
    code = p.code()
    assert p.yes(code).returncode == 0
    assert not (p.dir / "rounds/r5").exists() and (p.dir / "rounds/r4").is_dir()
    assert verdicts() == before


# ---------------------------------------------------------------- refusals (nothing written)

def test_not_a_git_repository_refuses(tmp_path):
    p = make(tmp_path, git=False)
    before = p.snapshot()
    refused_cleanly(p, p.run(), 1, "is not in a git repository", before, "")


def test_git_missing_cannot_run(tmp_path):
    p = make(tmp_path)
    before, status = p.snapshot(), p.status()
    r = p.run(env={"PATH": path_without(tmp_path, "git")})
    refused_cleanly(p, r, 3, "git not found on PATH", before, status)


def test_nothing_committed_refuses(tmp_path):
    p = make(tmp_path, commit=False)
    before = p.snapshot()
    refused_cleanly(p, p.run(), 1, "nothing is committed yet", before, p.status())


@pytest.mark.parametrize("marker", ["rebase-merge", "MERGE_HEAD", "CHERRY_PICK_HEAD"])
def test_a_rebase_in_progress_refuses(tmp_path, marker):
    p = make(tmp_path)
    (p.repo / ".git" / marker).mkdir() if marker == "rebase-merge" else (p.repo / ".git" / marker).write_text("0" * 40 + "\n")
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 1, "is in progress", before, status)


def test_a_modified_file_refuses(tmp_path):
    p = make(tmp_path)
    p.write("rounds/r2/mark.svg", "<svg>changed</svg>\n")
    before, status = p.snapshot(), p.status()
    r = p.run()
    refused_cleanly(p, r, 1, 'modified: "rounds/r2/mark.svg"', before, status)
    assert "could not be restored" in r.stderr


def test_a_staged_file_refuses(tmp_path):
    p = make(tmp_path)
    p.write("rounds/r2/mark.svg", "<svg>changed</svg>\n")
    p.git("add", "rounds/r2/mark.svg")
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 1, 'staged: "rounds/r2/mark.svg"', before, status)


def test_a_deleted_file_refuses(tmp_path):
    p = make(tmp_path)
    (p.dir / "rounds/r2/mark.svg").unlink()
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 1, 'deleted: "rounds/r2/mark.svg"', before, status)


def test_an_untracked_file_refuses(tmp_path):
    p = make(tmp_path)
    p.write("rounds/r2/new.png", "png\n")
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 1, 'not known to git: "rounds/r2/new.png"', before, status)


def test_an_ignored_file_other_than_ds_store_refuses(tmp_path):
    p = make(tmp_path)
    p.write(".gitignore", "*.tmp\n")
    p.commit()
    p.write("rounds/r2/scratch.tmp", "x\n")
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 1, 'not known to git: "rounds/r2/scratch.tmp"', before, status)


def test_an_assume_unchanged_file_refuses(tmp_path):
    p = make(tmp_path)
    p.git("update-index", "--assume-unchanged", "rounds/r2/mark.svg")
    p.write("rounds/r2/mark.svg", "<svg>edited, and git status does not show it</svg>\n")
    assert "mark.svg" not in p.git("status", "--porcelain").stdout
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 1, "assume-unchanged", before, status)


def test_a_skip_worktree_file_refuses(tmp_path):
    p = make(tmp_path)
    p.git("update-index", "--skip-worktree", "rounds/r2/mark.svg")
    p.write("rounds/r2/mark.svg", "<svg>edited, and git status does not show it</svg>\n")
    assert "mark.svg" not in p.git("status", "--porcelain").stdout
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 1, "skip-worktree", before, status)


@pytest.mark.parametrize("gitlink", [False, True])
def test_rounds_as_a_nested_repository_refuses(tmp_path, gitlink):
    p = make(tmp_path, git=False)
    p.git("init", "-q", "-b", "main")
    if gitlink:
        inner = p.repo / "rounds"
        p.git("init", "-q", "-b", "main", cwd=inner)
        p.git("add", "-A", cwd=inner)
        p.git("commit", "-q", "-m", "inner", cwd=inner)
        p.git("add", "-A")
        p.git("commit", "-q", "-m", "outer")
        assert "160000" in p.git("ls-files", "-s", "--", "rounds").stdout
    else:
        p.commit()
        (p.dir / "rounds" / ".git").mkdir()
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 1, "rounds/ is a git repository of its own", before, status)


def test_a_nested_repository_or_submodule_in_a_round_refuses(tmp_path):
    p = make(tmp_path)
    p.write("rounds/r2/sub/.git/HEAD", "ref: refs/heads/main\n")
    before, status = p.snapshot(), p.status()
    r = p.run()
    refused_cleanly(p, r, 1, "rounds/r2/sub", before, status)


def test_a_file_git_does_not_list_refuses(tmp_path, monkeypatch, capsys):
    p = make(tmp_path)
    p.write("rounds/r2/hidden.png", "x\n")
    for k, v in p.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(cleanup, "status_entries", lambda *a, **k: [])
    rc = cleanup.run_cli(["--project", str(p.dir)])
    err = capsys.readouterr().err
    assert rc == 1 and 'not known to git: "rounds/r2/hidden.png"' in err


def test_rounds_folder_symlink_refuses(tmp_path):
    p = make(tmp_path)
    shutil.move(p.dir / "rounds", tmp_path / "real-rounds")
    os.symlink(tmp_path / "real-rounds", p.dir / "rounds")
    p.commit()
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 2, "rounds is a symbolic link", before, status)


def test_a_round_folder_symlink_refuses(tmp_path):
    p = make(tmp_path)
    shutil.move(p.dir / "rounds/r2", tmp_path / "real-r2")
    os.symlink(tmp_path / "real-r2", p.dir / "rounds/r2")
    p.commit()
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 2, "rounds/r2 is a symbolic link", before, status)


def test_a_symlink_inside_a_candidate_refuses(tmp_path):
    p = make(tmp_path)
    os.symlink("mark.svg", p.dir / "rounds/r2/img")
    p.commit()
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 2, "rounds/r2/img", before, status)


def test_a_link_and_a_modified_file_exit_2(tmp_path):
    p = make(tmp_path)
    os.symlink("mark.svg", p.dir / "rounds/r2/img")
    p.commit()
    p.write("rounds/r3/mark.svg", "<svg>changed</svg>\n")
    before, status = p.snapshot(), p.status()
    r = p.run()
    refused_cleanly(p, r, 2, "symbolic link", before, status)
    assert "modified" not in r.stderr, "9a wins: the git state is not looked at"


@pytest.mark.parametrize("name", ["r03", "r٣"])
def test_a_round_folder_with_a_leading_zero_or_non_ascii_digit_refuses(tmp_path, name):
    p = make(tmp_path)
    p.write(f"rounds/{name}/board.html", board("refine", 3))
    p.commit()
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 2, f"rounds/{name} is read as round 3", before, status)


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_an_unreadable_source_refuses(tmp_path):
    p = make(tmp_path)
    f = p.write("research/notes.md", "x\n")
    p.commit()
    f.chmod(0)
    try:
        status = p.status()
        r = p.run()
        assert r.returncode == 1 and "cannot read research/notes.md" in r.stderr
        assert not (p.dir / "qa").exists() and p.status() == status
    finally:
        f.chmod(0o644)


def test_a_report_that_is_not_json_refuses(tmp_path):
    p = make(tmp_path)
    p.write("assets/_checks/page-check/bad.json", "{ not json\n")
    p.commit()
    before, status = p.snapshot(), p.status()
    refused_cleanly(p, p.run(), 1, "assets/_checks/page-check/bad.json: it is not valid JSON", before, status)


def test_git_environment_variables_are_ignored(tmp_path):
    p = make(tmp_path)
    other = make(tmp_path / "o", {0: "pick", 1: "refine"}, name="other")
    other_head, other_status = other.git("rev-parse", "HEAD").stdout, other.status()
    plain = p.run()
    env = {"GIT_DIR": str(other.repo / ".git"), "GIT_WORK_TREE": str(other.repo), "GIT_COMMON_DIR": str(other.repo / ".git"), "GIT_INDEX_FILE": str(other.repo / ".git" / "index"),
           "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.worktree", "GIT_CONFIG_VALUE_0": str(other.repo)}
    r = p.run(env=env)
    assert r.returncode == 0 and r.stdout == plain.stdout
    code = re.search(r"code: ([0-9a-f]{12})", r.stdout).group(1)
    assert p.run("--record-yes", code, "--said", "ok", env=env).returncode == 0
    assert p.run("--yes", code, env=env).returncode == 0
    assert not (p.dir / "rounds/r2").exists() and (p.dir / "rounds/r4").is_dir()
    assert other.git("rev-parse", "HEAD").stdout == other_head and other.status() == other_status and (other.dir / "rounds/r0/board.html").is_file()


# ---------------------------------------------------------------- .DS_Store

def test_ds_store_untracked_or_ignored_gives_the_same_plan(tmp_path):
    p = make(tmp_path)
    p.write("rounds/r2/.DS_Store", b"\x00\x00\x00\x01Bud1")
    (p.home / ".config" / "git").mkdir(parents=True)
    plain = p.run()
    (p.home / ".config" / "git" / "ignore").write_text(".DS_Store\n")
    ignored = p.run()
    assert plain.returncode == ignored.returncode == 0
    assert re.search(r"code: ([0-9a-f]{12})", plain.stdout).group(1) == re.search(r"code: ([0-9a-f]{12})", ignored.stdout).group(1)
    assert ".DS_Store" in plain.stdout and "not part of the code" in plain.stdout


def test_a_ds_store_written_after_the_yes_does_not_change_the_code(tmp_path):
    p = make(tmp_path)
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    p.write("rounds/r2/.DS_Store", b"\x00\x01")
    p.write("rounds/r3/.DS_Store", b"\x00\x02")
    assert p.code() == code
    r = p.run("--yes", code)
    assert r.returncode == 0, r.stderr
    assert not (p.dir / "rounds/r2").exists() and not (p.dir / "rounds/r3").exists()
    assert ".DS_Store" in (p.dir / "qa" / f"{DATE}-cleanup-removed.txt").read_text(encoding="utf-8")


def test_ds_store_is_deleted_and_the_empty_folder_goes(tmp_path):
    p = make(tmp_path)
    p.write("rounds/r2/deep/.DS_Store", b"\x00")
    code = p.code()
    assert p.yes(code).returncode == 0
    assert not (p.dir / "rounds/r2").exists()


# ---------------------------------------------------------------- the yes

def test_yes_without_a_recorded_yes_refuses(tmp_path):
    p = make(tmp_path)
    code = p.code()
    r = p.run("--yes", code)
    assert r.returncode == 1 and f"the owner's yes to plan {code} is not recorded" in r.stderr
    assert (p.dir / "rounds/r2").is_dir() and not p.git("diff", "--cached", "--name-only").stdout


def test_record_yes_without_a_shown_plan_refuses(tmp_path):
    p = make(tmp_path)
    code = p.code()
    (p.dir / "qa" / f"{DATE}-cleanup-plan.txt").unlink()
    r = p.run("--record-yes", code, "--said", "ok")
    assert r.returncode == 1 and f"no plan with code {code} was shown" in r.stderr
    assert (p.dir / "DECISIONS.md").read_text(encoding="utf-8").count("## ") == 0


def test_record_yes_with_another_code_refuses(tmp_path):
    p = make(tmp_path)
    p.code()
    r = p.run("--record-yes", "0" * 12, "--said", "ok")
    assert r.returncode == 1 and "no plan with code" in r.stderr
    assert "Cleanup plan" not in (p.dir / "DECISIONS.md").read_text(encoding="utf-8")


def test_a_plan_that_changed_after_the_yes_refuses(tmp_path):
    for way in ("reference", "file", "keep"):
        q = make(tmp_path / way)
        code = q.code()
        assert q.run("--record-yes", code, "--said", "ok").returncode == 0
        keeps = []
        if way == "reference":
            q.write("research/new.md", "now rounds/r2/mark.svg matters\n")
            q.commit()
        elif way == "file":
            q.write("rounds/r2/mark.svg", "<svg>committed again</svg>\n")
            q.commit()
        else:
            keeps = ["--keep", "r3"]
        r = q.run(*keeps, "--yes", code)
        assert r.returncode == 1 and "the plan changed since the owner said yes" in r.stderr, (way, r.stderr)
        assert (q.dir / "rounds/r2").is_dir() and not q.git("diff", "--cached", "--name-only").stdout


def test_a_yes_is_used_once_and_a_new_recorded_yes_allows_one_more_run(tmp_path):
    p = make(tmp_path)
    code = p.code()
    assert p.yes(code).returncode == 0
    record = (p.dir / "qa" / f"{DATE}-cleanup-removed.txt").read_text(encoding="utf-8")
    restore = re.search(r"^restore: (.*)$", record, re.M).group(1)
    assert subprocess.run(["bash", "-c", restore], capture_output=True, text=True, env={**os.environ, **p.env}).returncode == 0
    assert (p.dir / "rounds/r2/mark.svg").is_file()
    r = p.run("--yes", code)
    assert r.returncode == 1 and "was used on" in r.stderr and f"qa/{DATE}-cleanup-removed.txt" in r.stderr
    assert (p.dir / "rounds/r2").is_dir()
    assert p.run("--record-yes", code, "--said", "again, please").returncode == 0
    assert (p.dir / "DECISIONS.md").read_text(encoding="utf-8").count("- Cleanup plan: sha256:") == 2
    r = p.run("--yes", code)
    assert r.returncode == 0, r.stderr
    assert not (p.dir / "rounds/r2").exists() and (p.dir / "qa" / f"{DATE}-cleanup-removed-2.txt").is_file()


def test_record_yes_twice_for_an_unused_yes_writes_it_once(tmp_path):
    p = make(tmp_path)
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    r = p.run("--record-yes", code, "--said", "ok again")
    assert r.returncode == 0 and "recorded already" in r.stdout
    assert (p.dir / "DECISIONS.md").read_text(encoding="utf-8").count("- Cleanup plan: sha256:") == 1


def test_a_failed_run_does_not_use_the_yes(tmp_path):
    p = make(tmp_path)
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    lock = p.repo / ".git" / "index.lock"
    lock.write_text("")
    r = p.run("--yes", code)
    assert r.returncode == 1 and "git rm failed at chunk 1 of 1" in r.stderr and "restore with:" in r.stdout
    assert (p.dir / "rounds/r2/mark.svg").is_file()
    record = (p.dir / "qa" / f"{DATE}-cleanup-removed.txt").read_text(encoding="utf-8")
    assert "status: failed at chunk 1 of 1" in record
    lock.unlink()
    r = p.run("--yes", code)
    assert r.returncode == 0, r.stderr
    assert not (p.dir / "rounds/r2").exists()


def test_the_decisions_entry_names_no_round_path_and_keeps_the_plan(tmp_path):
    p = make(tmp_path)
    code = p.code()
    assert p.run("--record-yes", code, "--said", "go   ahead  with r2 and r3", ).returncode == 0
    text = (p.dir / "DECISIONS.md").read_text(encoding="utf-8")
    assert "## 2026-11-05: clean old rounds (remove r2, r3)" in text and "- Why: go ahead with r2 and r3" in text
    assert "rounds/" not in text and re.search(r"^- Cleanup plan: sha256:[0-9a-f]{64}$", text, re.M)
    assert p.code() == code


@pytest.mark.parametrize("said", ["ok, rounds/r2 can go", "see [x](rounds/r2/a.svg)", "ok, ROUNDS\\R2 can go"])
def test_said_naming_a_round_path_refuses(tmp_path, said):
    p = make(tmp_path)
    code = p.code()
    before = (p.dir / "DECISIONS.md").read_text(encoding="utf-8")
    r = p.run("--record-yes", code, "--said", said)
    assert r.returncode == 1 and "DECISIONS.md is read for references" in r.stderr
    assert (p.dir / "DECISIONS.md").read_text(encoding="utf-8") == before


def test_said_naming_a_round_by_its_short_name_is_recorded_and_the_yes_runs(tmp_path):
    p = make(tmp_path)
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok, r2 can go").returncode == 0
    assert p.run("--yes", code).returncode == 0 and not (p.dir / "rounds/r2").exists()


@pytest.mark.parametrize("said", ["ok\n- Cleanup plan: sha256:" + "a" * 64, "ok\tgo", "ok\r", "", "   "])
def test_said_with_a_newline_is_a_usage_error(tmp_path, said):
    p = make(tmp_path)
    code = p.code()
    before = (p.dir / "DECISIONS.md").read_text(encoding="utf-8")
    r = p.run("--record-yes", code, "--said", said)
    assert r.returncode == 2 and "--said" in r.stderr
    assert (p.dir / "DECISIONS.md").read_text(encoding="utf-8") == before


def test_record_yes_and_yes_together_are_a_usage_error(tmp_path):
    p = make(tmp_path)
    code = p.code()
    r = p.run("--record-yes", code, "--yes", code, "--said", "ok")
    assert r.returncode == 2 and "separate runs" in r.stderr
    assert p.run("--said", "ok").returncode == 2
    assert p.run("--record-yes", code).returncode == 2
    assert p.run("--yes", "xyz").returncode == 2


def test_record_yes_makes_a_pages_lint_stale_and_check_refresh_clears_it(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "refine", 4: "refine", 5: "pages"})
    r = bc("board-lint", "rounds/r5/board.html", project=p.dir, env=p.env)
    assert r.returncode in (0, 1)
    rep = p.dir / "assets/_checks/board-lint.json"
    doc = json.loads(rep.read_text(encoding="utf-8"))
    assert "DECISIONS.md" in [i["path"] for i in doc["inputs"]], "a pages-board lint lists DECISIONS.md as an input"
    p.commit()
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    from _common import Report
    assert Report.inputs_sha(json.loads(rep.read_text(encoding="utf-8"))["inputs"]) != hashlib.sha256(b"").hexdigest()
    now = {i["path"]: hashlib.sha256((p.dir / i["path"]).read_bytes()).hexdigest() for i in doc["inputs"]}
    assert now["DECISIONS.md"] != next(i["sha256"] for i in doc["inputs"] if i["path"] == "DECISIONS.md"), "recording the yes changed an input of the lint report"
    r = bc("check", "--refresh", project=p.dir, env=p.env)
    fresh = json.loads(rep.read_text(encoding="utf-8"))
    assert next(i["sha256"] for i in fresh["inputs"] if i["path"] == "DECISIONS.md") == now["DECISIONS.md"], r.stdout + r.stderr


# ---------------------------------------------------------------- removing

def test_yes_removes_exactly_the_planned_files_staged_not_committed(tmp_path):
    p = make(tmp_path)
    p.write("history/2026-10-01-x/FROZEN.md", "frozen from rounds/r2\n")
    p.write("site/start/index.html", "<html></html>\n")
    p.commit()
    head = p.git("rev-parse", "HEAD").stdout
    keep_before = {k: v for k, v in p.snapshot().items() if k.startswith(("history/", "site/", "rounds/r0", "rounds/r1", "rounds/r4"))}
    code = p.code()
    r = p.yes(code)
    assert r.returncode == 0, r.stderr
    assert p.git("rev-parse", "HEAD").stdout == head
    names = p.git("diff", "--cached", "--name-status").stdout.splitlines()
    assert sorted(names) == sorted(f"D\t{f}" for f in (f"rounds/r{n}/{x}" for n in (2, 3) for x in ("board.html", "mark.svg")))
    assert {k: v for k, v in p.snapshot().items() if k in keep_before} == keep_before
    assert "staged, not committed" in r.stdout and "suggested commit message: brand: remove old rounds r2, r3" in r.stdout and "check --refresh" in r.stdout
    assert not (p.dir / "rounds/r2").exists() and not (p.dir / "rounds/r3").exists()


ODD = ["a b ż.png", "-x.png", "*.png", "[1].png", "b.png", "it's \"quoted\".png"]


def test_paths_with_spaces_dashes_globs_and_unicode_are_removed_exactly(tmp_path):
    p = make(tmp_path)
    for name in ODD:
        p.write(f"rounds/r2/{name}", name)
        p.write(f"rounds/r4/{name}", name)
    p.commit()
    keep = p.snapshot()
    code = p.code()
    assert p.yes(code).returncode == 0
    for name in ODD:
        assert not (p.dir / "rounds/r2" / name).exists() and (p.dir / "rounds/r4" / name).read_text(encoding="utf-8") == name
    assert {k: v for k, v in p.snapshot().items() if k.startswith("rounds/r4")} == {k: v for k, v in keep.items() if k.startswith("rounds/r4")}


def test_a_path_with_a_newline_is_one_line_in_the_plan_and_removed(tmp_path):
    p = make(tmp_path)
    p.write("rounds/r2/a\nb.png", "x")
    p.commit()
    out = p.run().stdout
    assert '"rounds/r2/a\\nb.png"' in out and "\nb.png" not in out
    assert p.yes(p.code()).returncode == 0
    assert not (p.dir / "rounds/r2").exists()


def test_git_runs_without_a_shell_and_with_literal_pathspecs(tmp_path, monkeypatch, capsys):
    p = make(tmp_path)
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    for k, v in p.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("GIT_FOO_BAR", "1")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nowhere"))
    calls = []
    real = subprocess.run

    def spy(cmd, *a, **k):
        calls.append((cmd, k))
        return real(cmd, *a, **k)
    monkeypatch.setattr(cleanup.subprocess, "run", spy)
    assert cleanup.run_cli(["--project", str(p.dir), "--yes", code]) == 0
    assert calls
    for cmd, k in calls:
        assert isinstance(cmd, list) and cmd[0] == "git" and k.get("shell") is False and "--literal-pathspecs" in cmd
        assert not any(key.upper().startswith("GIT_") for key in k["env"]) and k["stdin"] == subprocess.DEVNULL
    rms = [c for c, _ in calls if "rm" in c[:8]]
    assert rms and all("--" in c and "-r" not in c and "-f" not in c and "--ignore-unmatch" not in c for c in rms)


def test_removal_is_chunked(tmp_path, monkeypatch):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "refine"})
    for i in range(8):
        p.write(f"rounds/r2/f{i}.png", str(i))
    p.commit()
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    for k, v in p.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(cleanup, "CHUNK_FILES", 3)
    calls = []
    real = subprocess.run
    monkeypatch.setattr(cleanup.subprocess, "run", lambda cmd, *a, **k: (calls.append(cmd), real(cmd, *a, **k))[1])
    assert cleanup.run_cli(["--project", str(p.dir), "--yes", code]) == 0
    assert len([c for c in calls if "rm" in c[:8]]) == 4
    assert not (p.dir / "rounds/r2").exists()


def test_a_failed_chunk_stops_and_records_what_was_removed(tmp_path, monkeypatch, capsys):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "refine"})
    for i in range(4):
        p.write(f"rounds/r2/f{i}.png", str(i))
    p.commit()
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    for k, v in p.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(cleanup, "CHUNK_FILES", 2)
    real, seen = subprocess.run, []

    def spy(cmd, *a, **k):
        if "rm" in cmd[:8]:
            seen.append(cmd)
            if len(seen) == 2:
                return subprocess.CompletedProcess(cmd, 1, b"", b"boom")
        return real(cmd, *a, **k)
    monkeypatch.setattr(cleanup.subprocess, "run", spy)
    rc = cleanup.run_cli(["--project", str(p.dir), "--yes", code])
    cap = capsys.readouterr()
    assert rc == 1 and "chunk 2 of 3" in cap.err and "restore with:" in cap.out
    record = (p.dir / "qa" / f"{DATE}-cleanup-removed.txt").read_text(encoding="utf-8")
    assert "status: failed at chunk 2 of 3: boom" in record and "removed files: 2" in record and "restore: git -C" in record
    assert len(p.git("diff", "--cached", "--name-only").stdout.split()) == 2
    # the staged deletions make every new run refuse until they are restored with the printed line, and the yes is still unused
    for args in ((), ("--yes", code)):
        r = p.run(*args)
        assert r.returncode == 1 and "an earlier removal failed" in r.stderr and "rounds/r2/f" in r.stderr and "git -C" in r.stderr and "checkout" in r.stderr, r.stderr
    restore = re.search(r"^restore: (.*)$", record, re.M).group(1)
    # the printed line is rebuilt from the record's checked fields, never copied from its restore: text, which anyone can edit
    rec_path = p.dir / "qa" / f"{DATE}-cleanup-removed.txt"
    rec_path.write_text(record.replace(f"restore: {restore}", "restore: touch PWNED; " + restore), encoding="utf-8")
    r = p.run()
    assert r.returncode == 1 and "PWNED" not in r.stderr and restore in r.stderr, r.stderr
    rec_path.write_text(re.sub(r"^head before: .*$", "head before: HEAD; touch PWNED", record, flags=re.M), encoding="utf-8")
    r = p.run()
    assert r.returncode == 1 and "PWNED" not in r.stderr and "damaged" in r.stderr, r.stderr
    rec_path.write_text(record, encoding="utf-8")
    assert subprocess.run(["bash", "-c", restore], capture_output=True, text=True, env={**os.environ, **p.env}).returncode == 0
    monkeypatch.undo()
    r = p.run("--yes", code)
    assert r.returncode == 0, r.stderr
    assert not (p.dir / "rounds/r2").exists()


def test_the_second_failed_record_of_a_day_is_the_one_that_counts(tmp_path, monkeypatch):
    # `-removed-2.txt` sorts before `-removed.txt` by name, so the newest record must be found by (date, k), not by name
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "refine", 4: "refine"})
    for i in range(4):
        p.write(f"rounds/r3/f{i}.png", str(i))
    p.commit()
    keep = ("--keep", "r3")
    code_a = p.code(*keep)
    assert p.run(*keep, "--record-yes", code_a, "--said", "ok").returncode == 0
    lock = p.repo / ".git" / "index.lock"
    lock.write_text("")
    r = p.run(*keep, "--yes", code_a)
    assert r.returncode == 1 and (p.dir / "qa" / f"{DATE}-cleanup-removed.txt").is_file()   # plan A: failed at chunk 1, nothing staged
    lock.unlink()
    keep = ("--keep", "r2")
    code_b = p.code(*keep)
    assert p.run(*keep, "--record-yes", code_b, "--said", "ok").returncode == 0
    for k, v in p.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(cleanup, "CHUNK_FILES", 2)
    real, seen = subprocess.run, []

    def spy(cmd, *a, **k):
        if "rm" in cmd[:8]:
            seen.append(cmd)
            if len(seen) == 2:
                return subprocess.CompletedProcess(cmd, 1, b"", b"boom")
        return real(cmd, *a, **k)
    monkeypatch.setattr(cleanup.subprocess, "run", spy)
    assert cleanup.run_cli(["--project", str(p.dir), *keep, "--yes", code_b]) == 1
    monkeypatch.undo()
    second = (p.dir / "qa" / f"{DATE}-cleanup-removed-2.txt").read_text(encoding="utf-8")
    assert "status: failed" in second and p.git("diff", "--cached", "--name-only").stdout.split()
    for args in ((), keep):
        r = p.run(*args)
        assert r.returncode == 1 and "an earlier removal failed (qa/" + f"{DATE}-cleanup-removed-2.txt" in r.stderr and "rounds/r3/" in r.stderr, (args, r.stdout, r.stderr)


def test_the_removed_record_restores_byte_for_byte(tmp_path):
    p = make(tmp_path)
    for name in ODD[:3]:
        p.write(f"rounds/r2/{name}", name)
    p.commit()
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    snap = {k: v for k, v in p.snapshot().items() if k.startswith("rounds/")}
    assert p.run("--yes", code).returncode == 0
    record = (p.dir / "qa" / f"{DATE}-cleanup-removed.txt").read_text(encoding="utf-8")
    assert "status: complete" in record and f"plan: sha256:" in record and "removed rounds: r2 r3" in record
    restore = re.search(r"^restore: (.*)$", record, re.M).group(1)
    assert subprocess.run(["bash", "-c", restore], capture_output=True, text=True, env={**os.environ, **p.env}).returncode == 0
    assert {k: v for k, v in p.snapshot().items() if k.startswith("rounds/")} == snap
    assert not p.git("diff", "--cached", "--name-only").stdout and p.git("diff", "--name-only").stdout.split() == ["DECISIONS.md"]


def test_the_restore_line_quotes_the_project_path(tmp_path):
    p = make(tmp_path, name='a "b" $c')
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    snap = {k: v for k, v in p.snapshot().items() if k.startswith("rounds/")}
    assert p.run("--yes", code).returncode == 0
    record = (p.dir / "qa" / f"{DATE}-cleanup-removed.txt").read_text(encoding="utf-8")
    restore = re.search(r"^restore: (.*)$", record, re.M).group(1)
    assert "'" in restore
    r = subprocess.run(["bash", "-c", restore], capture_output=True, text=True, env={**os.environ, **p.env})
    assert r.returncode == 0, r.stderr
    assert {k: v for k, v in p.snapshot().items() if k.startswith("rounds/")} == snap


def test_project_in_a_subfolder_of_the_repository(tmp_path):
    p = make(tmp_path, sub="brand")
    (p.repo / "other.txt").write_text("outside\n")
    (p.repo / "rounds" / "r2").mkdir(parents=True)
    (p.repo / "rounds" / "r2" / "keep.txt").write_text("not the project's\n")
    p.commit()
    out = p.run()
    assert out.returncode == 0 and parse_plan(out.stdout)[1] == {2, 3}, out.stderr
    assert p.yes(p.code()).returncode == 0
    assert not (p.dir / "rounds/r2").exists() and (p.repo / "rounds/r2/keep.txt").is_file() and (p.repo / "other.txt").is_file()
    assert sorted(p.git("diff", "--cached", "--name-only").stdout.split()) == sorted(f"brand/rounds/r{n}/{x}" for n in (2, 3) for x in ("board.html", "mark.svg"))


def test_nothing_to_clean_prints_the_keep_list_and_writes_nothing(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine"})
    before = p.snapshot()
    r = p.run()
    assert r.returncode == 0 and "nothing to clean: every round is kept" in r.stdout and p.snapshot() == before
    r = make(tmp_path / "none", {}).run()
    assert r.returncode == 0 and "nothing to clean" in r.stdout


def test_keep_of_a_round_that_does_not_exist_is_a_usage_error(tmp_path):
    p = make(tmp_path)
    r = p.run("--keep", "r9")
    assert r.returncode == 2 and "--keep r9: there is no rounds/r9/" in r.stderr
    assert p.run("--keep", "r03").returncode == 2


def test_help_needs_no_data_directory(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "BRAND_CREATOR_DATA"}
    r = subprocess.run([str(BIN), "cleanup", "--help"], capture_output=True, text=True, env=env, cwd=tmp_path)
    assert r.returncode == 0 and "--record-yes" in r.stdout and "--yes" in r.stdout and "no data directory" not in r.stderr
    top = subprocess.run([str(BIN), "help"], capture_output=True, text=True, env=env, cwd=tmp_path).stdout
    assert "cleanup " in top


# ---------------------------------------------------------------- loose reports, restore line, and the code the verifier found uncovered

LOOSE = "assets/_checks/page-check/rounds-r2-index.json"


def loose_project(tmp_path: Path, **kw) -> Proj:
    p = make(tmp_path, **kw)
    p.write("rounds/r2/index.html", "<html><body>x</body></html>\n")
    p.commit()
    p.write(LOOSE, json.dumps({"tool": "page-check/x", "run": {"target": {"page": "rounds/r2/index.html"}}, "inputs": []}))   # never committed
    return p


def test_the_restore_line_names_only_what_git_knows_and_works_with_a_loose_report(tmp_path):
    p = loose_project(tmp_path)
    code = p.code()
    r = p.yes(code)
    assert r.returncode == 0, r.stderr + r.stdout
    assert not (p.dir / LOOSE).exists() and not (p.dir / "rounds/r2").exists()
    line = re.search(r"^restore[^:]*: (git .*)$", r.stdout, re.M).group(1)
    assert LOOSE not in line
    record = (p.dir / "qa" / f"{DATE}-cleanup-removed.txt").read_text(encoding="utf-8")
    assert f"restore: {line}" in record
    cp = subprocess.run(["bash", "-c", line], capture_output=True, text=True, env={**os.environ, **p.env})
    assert cp.returncode == 0, cp.stderr
    assert (p.dir / "rounds/r2/board.html").is_file() and (p.dir / "rounds/r3/mark.svg").is_file() and not p.git("diff", "--cached", "--name-only").stdout.strip()


def test_a_loose_report_is_listed_deleted_and_part_of_the_code(tmp_path):
    plain = make(tmp_path / "a")
    plain.write("rounds/r2/index.html", "<html><body>x</body></html>\n")
    plain.commit()
    p = loose_project(tmp_path / "b")
    out = p.run().stdout
    assert f"not in git, deleted with the plan (it will not come back): \"{LOOSE}\"" in out
    assert "listed above, in the files to remove or as not in git" in out
    assert re.search(r"code: ([0-9a-f]{12})", out).group(1) != plain.code()


def test_an_uncommitted_change_in_a_report_of_a_removed_round_names_the_reports(tmp_path):
    p = make(tmp_path)
    p.write("rounds/r2/index.html", "<html><body>x</body></html>\n")
    p.write(LOOSE, json.dumps({"tool": "page-check/x", "run": {"target": {"page": "rounds/r2/index.html"}}, "inputs": []}))
    p.commit()
    p.write(LOOSE, json.dumps({"tool": "page-check/x", "run": {"target": {"page": "rounds/r2/index.html"}}, "inputs": [], "again": 1}))
    r = p.run()
    assert r.returncode == 1 and "in the rounds and reports to remove are not committed" in r.stderr and LOOSE in r.stderr


def test_a_loose_report_in_a_project_inside_a_subfolder_is_deleted(tmp_path):
    p = loose_project(tmp_path, sub="brand")
    assert p.yes(p.code()).returncode == 0
    assert not (p.dir / LOOSE).exists() and not (p.dir / "rounds/r2").exists()


def test_a_json_source_names_a_round_by_a_decoded_string(tmp_path):
    p = make(tmp_path)
    p.write("site/data.json", '{"hero": "rounds\\u002fr2/mark.svg"}\n')
    p.commit()
    kept, removed = parse_plan(p.run().stdout)
    assert 2 in kept and removed == {3}


def test_an_href_with_a_percent_encoded_round_keeps_it(tmp_path):
    p = make(tmp_path)
    p.write("site/index.html", '<html><body><a href="../rounds/%72%32/mark.svg">m</a></body></html>\n')
    p.commit()
    kept, removed = parse_plan(p.run().stdout)
    assert 2 in kept and removed == {3}


def test_a_binary_file_is_not_read_for_references(tmp_path):
    p = make(tmp_path)
    p.write("site/blob.bin", b"\0\1rounds/r2/mark.svg\n")
    p.commit()
    assert parse_plan(p.run().stdout)[1] == {2, 3}


def test_keep_of_a_round_that_is_kept_already_still_changes_the_code(tmp_path):
    p = make(tmp_path)
    assert p.code() != p.code("--keep", "r4")


def test_a_kept_site_board_keeps_the_references_board_it_reads(tmp_path):
    p = make(tmp_path, {0: "style", 1: "pick", 2: "refine", 3: "none", 4: "hero", 5: "none", 6: "hero"})
    groups = "".join(f'<section data-section="group" data-name="g{i}"><h2>g</h2><p>a site</p></section>' for i in range(4))
    for n in (3, 5):
        p.write(f"rounds/r{n}/board.html", board("site-refs", n, body=groups))
    p.commit()
    out = p.run().stdout
    assert 3 in parse_plan(out)[0] and "website references board" in reasons(out, 3), out


def test_a_failed_post_condition_exits_1_and_is_recorded(tmp_path, monkeypatch, capsys):
    p = make(tmp_path)
    code = p.code()
    assert p.run("--record-yes", code, "--said", "go").returncode == 0
    for k, v in p.env.items():
        monkeypatch.setenv(k, v)
    calls = []
    real = cleanup.verify_history
    monkeypatch.setattr(cleanup, "verify_history", lambda *a, **k: (calls.append(1), real(*a, **k) if len(calls) == 1 else {"history/x": "changed"})[1])
    rc = cleanup.run_cli(["--project", str(p.dir), "--yes", code])
    err = capsys.readouterr().err
    assert rc == 1 and "history/ is not as it was" in err
    assert "status: failed: post-conditions" in (p.dir / "qa" / f"{DATE}-cleanup-removed.txt").read_text(encoding="utf-8")


def test_said_with_a_bidi_control_is_a_usage_error(tmp_path):
    p = make(tmp_path)
    code = p.code()
    r = p.run("--record-yes", code, "--said", "ok ‮ go")
    assert r.returncode == 2 and "--said" in r.stderr


def test_removal_is_chunked_by_path_bytes(tmp_path, monkeypatch):
    p = make(tmp_path)
    for i in range(8):
        p.write(f"rounds/r2/f{i}.png", str(i))
    p.commit()
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    for k, v in p.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(cleanup, "CHUNK_BYTES", 40)
    calls = []
    real = subprocess.run
    monkeypatch.setattr(cleanup.subprocess, "run", lambda cmd, *a, **k: (calls.append(cmd), real(cmd, *a, **k))[1])
    assert cleanup.run_cli(["--project", str(p.dir), "--yes", code]) == 0
    rms = [c for c in calls if "rm" in c[:8]]
    assert len(rms) >= 5
    for c in rms:
        paths = c[c.index("--") + 1:]
        assert len(paths) == 1 or sum(len(x.encode()) + 1 for x in paths) <= 40
    assert not (p.dir / "rounds/r2").exists()


def test_the_file_list_is_checked_again_just_before_removing(tmp_path, monkeypatch, capsys):
    p = make(tmp_path)
    p.write("rounds/r2/extra.png", "x")
    p.commit()
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    for k, v in p.env.items():
        monkeypatch.setenv(k, v)
    real, n = cleanup.check_git_state, []

    def second_differs(*a, **k):
        n.append(1)
        out = real(*a, **k)
        return out._replace(files=out.files[:-1]) if len(n) == 2 else out
    monkeypatch.setattr(cleanup, "check_git_state", second_differs)
    rc = cleanup.run_cli(["--project", str(p.dir), "--yes", code])
    assert rc == 1 and "the plan changed while cleanup ran" in capsys.readouterr().err and len(n) == 2
    assert (p.dir / "rounds/r2/board.html").is_file() and not p.git("diff", "--cached", "--name-only").stdout.strip()


def test_the_decision_names_the_plan_file_that_holds_the_hash(tmp_path):
    p = make(tmp_path)
    code = p.code()
    assert (p.dir / "qa" / f"{DATE}-cleanup-plan.txt").is_file()
    r = p.run("--record-yes", code, "--said", "ok", env={"BRAND_CREATOR_TODAY": "2026-11-07"})
    assert r.returncode == 0, r.stderr
    text = (p.dir / "DECISIONS.md").read_text(encoding="utf-8")
    assert f"the plan is qa/{DATE}-cleanup-plan.txt;" in text and "2026-11-07-cleanup-plan" not in text


# ---------------------------------------------------------------- review round 1

def test_a_failed_record_is_settled_by_a_later_complete_run_of_the_same_plan(tmp_path):
    p = make(tmp_path)
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    lock = p.repo / ".git" / "index.lock"
    lock.write_text("")
    assert p.run("--yes", code).returncode == 1
    lock.unlink()
    assert p.run("--yes", code).returncode == 0
    r = p.run()   # r2 and r3 are still staged as deleted: the failed record no longer counts
    assert r.returncode == 0, r.stderr
    p.git("commit", "-q", "-m", "clean")
    p.write("rounds/r5/board.html", board("refine", 5))
    p.git("add", "rounds/r5")
    r = p.run()   # a staged new round is not the failed run's deletion
    assert r.returncode == 0, r.stderr


def test_a_failed_record_is_settled_by_a_later_complete_run_of_another_plan(tmp_path):
    p = make(tmp_path)
    code = p.code("--keep", "r3")
    assert p.run("--keep", "r3", "--record-yes", code, "--said", "ok").returncode == 0
    lock = p.repo / ".git" / "index.lock"
    lock.write_text("")
    assert p.run("--keep", "r3", "--yes", code).returncode == 1
    lock.unlink()
    code_b = p.code()
    assert code_b != code
    assert p.run("--record-yes", code_b, "--said", "ok").returncode == 0
    assert p.run("--yes", code_b).returncode == 0
    r = p.run()   # the complete run staged r2 and r3 on purpose: the failed record of the other plan does not count
    assert r.returncode == 0, r.stderr


def test_a_staged_new_round_is_not_a_failed_runs_deletion(tmp_path, monkeypatch):
    p = make(tmp_path)
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    lock = p.repo / ".git" / "index.lock"
    lock.write_text("")
    assert p.run("--yes", code).returncode == 1
    lock.unlink()
    p.write("rounds/r5/board.html", board("refine", 5))
    p.git("add", "rounds/r5")
    r = p.run()
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("copy", ["rounds/r5/board.html", "history/2026-11-01-r2/mark.svg"])
def test_a_staged_file_similar_to_a_removed_one_is_no_failure(tmp_path, copy):
    p = make(tmp_path)
    big = "".join(f"<section>line {i} of a long shared template</section>\n" for i in range(40))
    p.write("rounds/r2/board.html", board("refine", 2, body=big))
    p.commit("template")
    if copy.startswith("rounds"):
        p.write(copy, board("refine", 5, body=big) + "<p>x</p>\n")
    else:
        p.write(copy, (p.dir / "rounds/r2/mark.svg").read_bytes())
    p.git("add", copy)
    r = p.yes(p.code())
    assert r.returncode == 0, r.stderr
    assert "status: complete" in (p.dir / "qa" / f"{DATE}-cleanup-removed.txt").read_text(encoding="utf-8")


def test_a_report_in_an_ignored_folder_is_a_loose_report(tmp_path):
    p = make(tmp_path)
    p.write("rounds/r2/index.html", "<html><body>x</body></html>\n")
    p.write(".gitignore", "assets/_checks/\n")
    p.commit()
    p.write(LOOSE, json.dumps({"tool": "page-check/x", "run": {"target": {"page": "rounds/r2/index.html"}}, "inputs": []}))
    r = p.run()
    assert r.returncode == 0, r.stderr
    assert f"not in git, deleted with the plan (it will not come back): \"{LOOSE}\"" in r.stdout


@pytest.mark.requires_macos
def test_a_file_named_decomposed_on_disk_and_committed_is_known_to_git(tmp_path):
    p = make(tmp_path)
    nfd = "rounds/r2/ża.png"
    p.write(nfd, b"png")
    p.commit()
    # git init on macOS sets core.precomposeunicode; without it this test proves nothing, so it fails rather than skips
    assert p.git("config", "--bool", "core.precomposeunicode", check=False).stdout.strip() == "true"
    r = p.run()
    assert r.returncode == 0, r.stderr


def test_record_yes_keeps_the_line_endings_of_decisions_md(tmp_path):
    p = make(tmp_path)
    old = b"# Acme: decisions\r\n\r\n## 2026-01-01: x\r\n\r\n- Gate: G1\r\n"
    p.write("DECISIONS.md", old)
    p.commit()
    code = p.code()
    assert p.run("--record-yes", code, "--said", "ok").returncode == 0
    new = (p.dir / "DECISIONS.md").read_bytes()
    assert new.startswith(old) and b"\n" not in new.replace(b"\r\n", b"")


# ---------------------------------------------------------------- cleanup --history: frozen rounds slimmed to what their boards show

FZ = "history/2026-10-21-approved"
HPNG = b"\x89PNG\r\n\x1a\n"


def frozen(tmp_path: Path, files: dict[str, str | bytes] | None = None, *, sub: str = "") -> Proj:
    """A committed project whose history/ holds one freeze: a board that shows shots/a.png, a build script, FROZEN.md, and _lead/big.png that no board shows."""
    p = make(tmp_path, {1: "pick"}, sub=sub)
    files = files if files is not None else {"board.html": '<img src="shots/a.png">', "shots/a.png": HPNG, "build.py": "print(1)\n",
                                             "FROZEN.md": "# Kept as written\n", "_lead/big.png": HPNG * 1000}
    entries = {}
    for rel, data in files.items():
        f = p.write(f"{FZ}/{rel}", data)
        entries[f"2026-10-21-approved/{rel}"] = hashlib.sha256(f.read_bytes()).hexdigest()
    p.write("history/MANIFEST.sha256", "".join(f"{h}  {r}\n" for r, h in sorted(entries.items())))
    p.commit("frozen")
    return p


def hcode(p: Proj) -> str:
    r = p.run("--history", "--static")
    assert r.returncode == 0, r.stderr + r.stdout
    return re.search(r"code: ([0-9a-f]{12})", r.stdout).group(1)


def manifest_paths(p: Proj) -> list[str]:
    return sorted(ln.split("  ", 1)[1] for ln in (p.dir / "history" / "MANIFEST.sha256").read_text().splitlines() if ln.strip())


def test_history_plan_lists_what_each_freeze_keeps_and_what_goes_with_sizes(tmp_path):
    p = frozen(tmp_path)
    r = p.run("--history", "--static")
    assert r.returncode == 0, r.stderr + r.stdout
    assert "2026-10-21-approved: stays 4 files" in r.stdout and "goes 1 files" in r.stdout
    assert '"history/2026-10-21-approved/_lead/big.png"' in r.stdout
    assert (p.dir / "qa" / f"{DATE}-cleanup-plan-history.txt").is_file()
    assert (p.dir / FZ / "_lead" / "big.png").is_file()                                   # the dry run removes nothing


def test_history_yes_removes_only_what_the_plan_listed_and_rewrites_the_manifest(tmp_path):
    p = frozen(tmp_path)
    code = hcode(p)
    assert p.run("--history", "--static", "--record-yes", code, "--said", "tak").returncode == 0
    r = p.run("--history", "--static", "--yes", code)
    assert r.returncode == 0, r.stderr + r.stdout
    assert not (p.dir / FZ / "_lead").exists() and (p.dir / FZ / "shots" / "a.png").is_file() and (p.dir / FZ / "build.py").is_file()
    assert manifest_paths(p) == ["2026-10-21-approved/FROZEN.md", "2026-10-21-approved/board.html", "2026-10-21-approved/build.py",
                                 "2026-10-21-approved/shots/a.png"]
    from _common import verify_history
    assert verify_history(p.dir) == []
    st = p.git("status", "--porcelain").stdout
    assert f"D  {FZ}/_lead/big.png" in st and "M  history/MANIFEST.sha256" in st     # staged, not committed
    assert "Cleanup plan: sha256:" in (p.dir / "DECISIONS.md").read_text()


def test_history_refuses_a_freeze_whose_files_do_not_match_the_manifest(tmp_path):
    p = frozen(tmp_path)
    (p.dir / FZ / "board.html").write_text('<img src="shots/a.png"><p>edited</p>')
    r = p.run("--history", "--static")
    assert r.returncode == 1 and "modified: history/2026-10-21-approved/board.html" in r.stderr
    assert not (p.dir / "qa" / f"{DATE}-cleanup-plan-history.txt").exists()


def test_history_record_restores_the_freeze_and_the_manifest(tmp_path):
    p = frozen(tmp_path)
    code = hcode(p)
    p.run("--history", "--static", "--record-yes", code, "--said", "tak")
    assert p.run("--history", "--static", "--yes", code).returncode == 0
    rec = (p.dir / "qa" / f"{DATE}-cleanup-removed-history.txt").read_text()
    assert "removed from history: 2026-10-21-approved" in rec
    restore = re.search(r"^restore: (.*)$", rec, re.M).group(1)
    assert subprocess.run(restore, shell=True, capture_output=True, env={**os.environ, "HOME": str(p.home)}).returncode == 0
    assert (p.dir / FZ / "_lead" / "big.png").read_bytes() == HPNG * 1000
    from _common import verify_history
    assert verify_history(p.dir) == []


def test_history_and_keep_refuse_each_other(tmp_path):
    p = frozen(tmp_path)
    r = p.run("--history", "--keep", "r1")
    assert r.returncode == 2 and "--history" in r.stderr and "--keep" in r.stderr


def test_history_static_goes_only_with_history(tmp_path):
    p = frozen(tmp_path)
    r = p.run("--static")
    assert r.returncode == 2 and "--static" in r.stderr


def test_history_without_a_browser_names_static(tmp_path):
    p = frozen(tmp_path)
    r = bc("cleanup", "--history", project=p.dir, env=p.env, data=tmp_path / "nodata")
    assert r.returncode == 3 and "--static" in r.stderr


def test_history_with_nothing_to_slim_says_so(tmp_path):
    p = frozen(tmp_path, {"board.html": '<img src="a.png">', "a.png": HPNG, "FROZEN.md": "# Kept as written\n"})
    r = p.run("--history", "--static")
    assert r.returncode == 0 and "nothing to slim in history/" in r.stdout


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_history_keeps_a_picture_a_frozen_board_adds_with_a_script(tmp_path):
    board = '<div id="g"></div><script>const i = document.createElement("img"); i.src = "shots/" + "late" + ".png"; g.append(i);</script>'
    p = frozen(tmp_path, {"board.html": board, "shots/late.png": HPNG, "shots/unseen.png": HPNG, "FROZEN.md": "# Kept as written\n"})
    r = p.run("--history")
    assert r.returncode == 0, r.stderr + r.stdout
    assert '"history/2026-10-21-approved/shots/unseen.png"' in r.stdout and "shots/late.png" not in r.stdout


def test_history_refuses_a_folder_freeze_did_not_name_and_never_puts_it_in_a_restore_line(tmp_path):
    p = frozen(tmp_path)
    odd = "2026-10-22-x; touch PWNED"
    p.write(f"history/{odd}/big.png", HPNG)
    mf = p.dir / "history" / "MANIFEST.sha256"
    mf.write_text(mf.read_text() + f"{hashlib.sha256(HPNG).hexdigest()}  {odd}/big.png\n")
    p.commit("odd folder")
    r = p.run("--history", "--static")
    assert r.returncode == 1 and "not a frozen round" in r.stderr and json.dumps(f"history/{odd}") in r.stderr
    assert "touch PWNED" not in r.stdout
    assert not (p.dir / "qa" / f"{DATE}-cleanup-plan-history.txt").exists()


def test_history_works_for_a_project_in_a_folder_of_a_bigger_repository(tmp_path):
    """The pilot brand lives in projects-brands/pilot: git prints paths from the repository root in status and from the project in ls-files."""
    p = frozen(tmp_path, sub="pilot")
    code = hcode(p)
    assert p.run("--history", "--static", "--record-yes", code, "--said", "tak").returncode == 0
    r = p.run("--history", "--static", "--yes", code)
    assert r.returncode == 0, r.stderr + r.stdout
    assert not (p.dir / FZ / "_lead").exists() and (p.dir / FZ / "shots" / "a.png").is_file()
    assert "D  pilot/history/2026-10-21-approved/_lead/big.png" in p.git("status", "--porcelain").stdout


# ---------------------------------------------------------------- review fixes (0.10.0)

def test_record_order_reads_history_records_and_breaks_a_same_day_tie_by_time(tmp_path):
    names = ["2026-11-05-cleanup-removed-history.txt", "2026-11-05-cleanup-removed-history-2.txt", "2026-11-05-cleanup-removed.txt", "2026-11-04-cleanup-removed-3.txt"]
    for i, n in enumerate(names):
        f = tmp_path / n
        f.write_text("x")
        os.utime(f, ns=(10**18 + i * 10**9, 10**18 + i * 10**9))   # written in the order listed
    got = [f.name for f in sorted(tmp_path.iterdir(), key=cleanup.record_order)]
    assert got == ["2026-11-04-cleanup-removed-3.txt", "2026-11-05-cleanup-removed-history.txt", "2026-11-05-cleanup-removed-history-2.txt",
                   "2026-11-05-cleanup-removed.txt"]


def test_history_removes_a_decomposed_polish_name_and_its_manifest_entry(tmp_path):
    import unicodedata
    nfd = unicodedata.normalize("NFD", "_lead/zdjęcie.png")
    p = frozen(tmp_path, {"board.html": '<img src="a.png">', "a.png": HPNG, "FROZEN.md": "# Kept as written\n", nfd: HPNG * 50})
    code = hcode(p)
    assert p.run("--history", "--static", "--record-yes", code, "--said", "tak").returncode == 0
    r = p.run("--history", "--static", "--yes", code)
    assert r.returncode == 0, r.stderr + r.stdout
    assert manifest_paths(p) == ["2026-10-21-approved/FROZEN.md", "2026-10-21-approved/a.png", "2026-10-21-approved/board.html"]
    from _common import verify_history
    assert verify_history(p.dir) == []
