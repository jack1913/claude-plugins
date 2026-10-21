"""Static checks over evals/ (no billed run): every case against the documented `claude plugin eval` schema, graders that
reference real things, fixtures that behave, and sample inputs that prove each key regex matches what it should (in the
JSON-encoded form the runner matches against).

The documented format (code.claude.com "Test plugins with evals", saved by the author as verify/plugin-evals.md): a case is a
directory with prompt.md (frontmatter = run fields, body = the prompt), an optional case.yaml (schema_version "1.1", name,
context.scaffold_script) and graders/*.md (frontmatter: type + options). An unknown prompt.md key is a load error in the real
loader, but an unknown grader key is silently ignored, so a misspelt option would never fail: the key sets are checked here.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from helpers import ROOT, bc, mutate

EVALS = ROOT / "evals"
SKILLS = ROOT / "skills"
README = ROOT / "docs" / "internals" / "evals.md"   # the page that documents how to run the evals
CONTRACT = ROOT / "scripts" / "CONTRACT.md"

PROMPT_KEYS = {"schema_version", "name", "description", "tags", "plugins", "runs", "expected_outcome", "model", "max_turns",
               "timeout_seconds", "allowed_tools", "disallowed_tools", "artifact_publish", "growthbook_overrides",
               "append_system_prompt", "env"}          # the loader's own list (printed by its "unknown frontmatter key" error)
GRADER_KEYS = {
    "regex": {"type", "weight", "arm", "pattern", "flags", "match", "target"},
    "tool_used": {"type", "weight", "arm", "tool", "input_match", "min", "max"},
    "file_exists": {"type", "weight", "arm", "path", "exists"},
    "llm": {"type", "weight", "arm", "focus"},
}
KNOWN_TOOLS = {"Read", "Glob", "Grep", "NotebookRead", "Skill", "AskUserQuestion", "Agent", "TodoWrite", "Bash", "Write", "Edit",
               "WebFetch", "WebSearch", "Workflow"}
TARGETS = {"last_message", "trace", "files", "mock_calls"}
PLAN_BULLETS = {   # plan-v2 evals row (and the three GAP resolutions) -> the case that carries it
    "stops at gate": "stops-at-gate-g2",
    "no writes to adoption targets before G6": "no-adoption-writes-before-g6",
    "never 'available'": "never-says-available",
    "no git commit without an ask": "no-git-commit-without-ask",
    "G0 asks scope before any board": "g0-asks-scope-before-board",
    "no open-ended feelings question": "no-open-feelings-question",
    "r1 board has map + Today + None of these": "r1-board-map-today-none",
    "bare '1' with two lists": "bare-number-two-lists",
    "'refine with style 2 and 3'": "refine-style-2-and-3",
    "rule change -> cascade run": "rule-change-runs-cascade",
    "judge shown with lead view + middle option": "judge-view-lead-view-middle-option",
    "bakery: no family/pixel/platform, no registry, first board": "bakery-first-board",
    "photographer: the same, in Polish": "photographer-first-board-pl",
    "single-thread: no Agent call before fleet approval": "single-thread-no-agent-before-fleet-approval",
    "architecture asked when a parent is shown (S2-P0-p2)": "architecture-asked-when-parent-shown",
    "architecture inferred when nothing shows one": "architecture-standalone-stated",
    "buy the domain / file the trademark (S2-P13-t2, S2-P2-g1, S7-F13)": "outward-actions-hand-off",
    "style research before the first board (G1s); without web tools it says so and stops": "style-gate-before-first-board",
}


# ---- a reader for the small YAML subset the cases use (flow lists and maps, single-quoted strings, one line per key) ---------------
def scalar(s: str):
    s = s.strip()
    if s.startswith("'"):
        assert s.endswith("'") and len(s) >= 2, s
        return s[1:-1].replace("''", "'")
    if s.startswith('"'):
        return json.loads(s)
    if s.startswith("["):
        assert s.endswith("]"), s
        inner = s[1:-1].strip()
        return [scalar(x) for x in inner.split(",")] if inner else []
    if s.startswith("{"):
        assert s.endswith("}"), s
        out = {}
        for part in s[1:-1].split(","):
            k, v = part.split(":", 1)
            out[k.strip()] = scalar(v)
        return out
    if s in ("true", "false"):
        return s == "true"
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path}: frontmatter must start on line 1"
    end = text.index("\n---\n", 4)
    fm = {}
    for line in text[4:end].splitlines():
        m = re.fullmatch(r"([A-Za-z_]+): (.*)", line)
        assert m, f"{path}: one `key: value` per line ({line!r})"
        assert m.group(1) not in fm, f"{path}: duplicate key {m.group(1)}"
        fm[m.group(1)] = scalar(m.group(2))
    return fm, text[end + 5:].strip()


def case_yaml(path: Path):
    out, ctx = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        m = re.fullmatch(r"( *)([A-Za-z_]+):(?: (.*))?", line)
        assert m, f"{path}: {line!r}"
        indent, k, v = len(m.group(1)), m.group(2), m.group(3)
        if indent == 0:
            if v is None:
                out[k] = ctx = {}
            else:
                out[k] = scalar(v)
                ctx = None
        else:
            assert ctx is not None and indent == 2, f"{path}: {line!r}"
            ctx[k] = scalar(v)
    return out


def case_dirs():
    return sorted(p for p in EVALS.iterdir() if p.is_dir() and not p.name.startswith("_") and p.name != "results")


def graders(case: Path):
    return {p.stem: frontmatter(p) for p in sorted((case / "graders").glob("*.md"))}


def prompt(case: Path):
    return frontmatter(case / "prompt.md")


def subcommands() -> set[str]:
    text = (ROOT / "bin" / "brand-creator").read_text(encoding="utf-8")
    usage = text[text.index("cat <<'EOF'"):text.index("\nEOF\n")]
    return set(re.findall(r"^  ([a-z][a-z0-9-]*)\b", usage, re.M))


def granted_tools() -> set[str]:
    """The tools the evals page's documented eval command grants (the run itself strips every tool that is not granted)."""
    t = README.read_text(encoding="utf-8")
    m = re.search(r"--allow-tools ((?:[A-Za-z]+ ?)+)", t[t.index("## Running the evals"):])
    assert m, "evals.md: the eval command must show --allow-tools"
    return set(m.group(1).split())


def scaffold(case: Path, ws: Path) -> Path | None:
    cy = case / "case.yaml"
    if not cy.exists():
        return None
    script = case_yaml(cy)["context"]["scaffold_script"]
    r = subprocess.run(["bash", str(case / script)], cwd=ws, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"{case.name}: scaffold failed: {r.stderr}"
    return ws


def tree(ws: Path) -> set[str]:
    return {p.relative_to(ws).as_posix() for p in ws.rglob("*") if ".git/" not in p.as_posix() + "/"}


# ---- structure ------------------------------------------------------------------------------------------------------------------
def test_there_is_one_case_per_plan_bullet_and_nothing_else():
    assert sorted(p.name for p in case_dirs()) == sorted(PLAN_BULLETS.values())
    assert len(set(PLAN_BULLETS.values())) == len(PLAN_BULLETS)


def test_every_case_follows_the_documented_layout_and_limits():
    granted = granted_tools()
    for c in case_dirs():
        fm, body = prompt(c)
        assert set(fm) <= PROMPT_KEYS, (c.name, set(fm) - PROMPT_KEYS)
        assert fm.get("name", c.name) == c.name
        assert body and "TODO" not in body, c.name
        assert 40 <= fm["max_turns"] <= 200, f"{c.name}: plan-v2 asks max_turns >= 40 (the runner's cap is 200)"
        assert 300 <= fm["timeout_seconds"] <= 3600, c.name
        assert 1 <= fm.get("runs", 3) <= 50 and isinstance(fm["tags"], list) and fm["tags"], c.name
        assert fm["description"].strip() and fm["expected_outcome"].strip(), c.name
        tools = fm["allowed_tools"]
        assert tools and set(tools) <= KNOWN_TOOLS, (c.name, set(tools) - KNOWN_TOOLS)
        assert "Skill" in tools, f"{c.name}: the plugin's skills load through the Skill tool"
        assert {"Bash", "Write", "Edit"} <= set(tools) <= KNOWN_TOOLS and {"Bash", "Write", "Edit"} <= granted, c.name
        if (c / "case.yaml").exists():
            cy = case_yaml(c / "case.yaml")
            assert cy["schema_version"] == "1.1" and cy["name"] == c.name and set(cy) == {"schema_version", "name", "context"}, c.name
            script = c / cy["context"]["scaffold_script"]
            assert set(cy["context"]) == {"scaffold_script"} and script.is_file(), c.name
            assert script.stat().st_mode & 0o111, f"{script} must be executable"
            assert script.read_text().startswith("#!/usr/bin/env bash\n"), script


def test_every_grader_has_a_valid_shape_and_every_case_checks_both_the_steps_and_the_result():
    for c in case_dirs():
        gs = graders(c)
        assert gs, c.name
        kinds = []
        for name, (fm, body) in gs.items():
            t = fm["type"]
            assert t in GRADER_KEYS, (c.name, name, t)
            assert set(fm) <= GRADER_KEYS[t], f"{c.name}/{name}: key the loader would silently ignore: {set(fm) - GRADER_KEYS[t]}"
            assert isinstance(fm["weight"], (int, float)) and fm["weight"] > 0, (c.name, name)
            if t == "regex":
                assert not re.search(r"\(\?[a-z]+\)", fm["pattern"]), f"{c.name}/{name}: inline flags are not supported; use `flags`"
                assert fm.get("flags", "i") in ("i", ""), (c.name, name)
                re.compile(fm["pattern"])
                assert fm.get("match", "contains") in ("contains", "not_contains") or re.fullmatch(r"count:\d+", fm["match"])
                tg = fm["target"]
                assert (isinstance(tg, dict) and set(tg) == {"source", "path"} and tg["source"] == "file") or (isinstance(tg, str) and tg in TARGETS), (c.name, name, tg)
            elif t == "tool_used":
                assert fm["tool"] in KNOWN_TOOLS, (c.name, name, fm["tool"])
                if "input_match" in fm:
                    assert not re.search(r"\(\?[a-z]+\)", fm["input_match"]), (c.name, name)
                    re.compile(fm["input_match"])
                mn, mx = fm.get("min", 1), fm.get("max", 10**9)
                assert mn <= mx, f"{c.name}/{name}: min {mn} > max {mx} can never pass (`min` defaults to 1; 'never called' needs min: 0 and max: 0)"
                if mx == 0:
                    assert mn == 0, (c.name, name)
                allowed = set(prompt(c)[0]["allowed_tools"])
                assert fm["tool"] in allowed or fm["tool"] == "Workflow", f"{c.name}/{name}: {fm['tool']} is not in allowed_tools"
            elif t == "file_exists":
                assert isinstance(fm["path"], str) and fm.get("exists", True) in (True, False), (c.name, name)
            else:
                assert fm["focus"] in ("last_message", "trace"), (c.name, name)
                assert body.count("PASS") >= 1 and body.count("FAIL") >= 1, f"{c.name}/{name}: a rubric states PASS and FAIL conditions"
            kinds.append((t, fm.get("tool"), fm.get("max")))
        assert any(t == "tool_used" and tool != "Skill" for t, tool, _ in kinds), f"{c.name}: needs a tool_used grader on the steps"
        assert any(t in ("regex", "file_exists", "llm") for t, _, _ in kinds), f"{c.name}: needs a grader on the result"
        assert sum(1 for t, *_ in kinds if t == "llm") <= 1, f"{c.name}: at most one judge call per run keeps the cost down"


# ---- graders that reference something real --------------------------------------------------------------------------------------
def test_graders_name_real_skills_subcommands_flags_and_board_attributes():
    subs = subcommands()
    scripts = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "scripts").rglob("*") if p.suffix in (".py", ".mjs", ".sh"))
    scripts += (ROOT / "bin" / "brand-creator").read_text()
    contract = CONTRACT.read_text(encoding="utf-8")
    template = (ROOT / "templates" / "round-page.html").read_text(encoding="utf-8")
    skills = {p.name for p in SKILLS.iterdir() if (p / "SKILL.md").is_file()}
    seen = {"skill": 0, "sub": 0, "flag": 0, "attr": 0}
    for c in case_dirs():
        for name, (fm, _) in graders(c).items():
            pat = fm.get("input_match") or fm.get("pattern") or ""
            where = f"{c.name}/{name}"
            if fm.get("tool") == "Skill":
                m = re.search(r"\(\?:\[\\w-\]\+:\)\?([a-z-]+)", pat)
                assert m and m.group(1) in skills, f"{where}: unknown skill"
                seen["skill"] += 1
            if fm.get("tool") == "Bash" and "brand-creator" in pat:
                words = {w for g in re.findall(r"\(\?:([a-z|-]+)\)", pat) for w in g.split("|")} | set(re.findall(r"\\b([a-z][a-z-]+)\\b", pat))
                words |= {w for w in re.findall(r"\\s([a-z][a-z-]+)\\s", pat)}
                words -= {"brand", "creator"}
                assert words and words <= subs, f"{where}: not brand-creator subcommands: {words - subs}"
                seen["sub"] += 1
            for flag in re.findall(r"--[a-z][a-z-]+", pat):
                assert flag in scripts or flag in ("--no-verify", "--no-hooks", "--data", "--form", "--post"), f"{where}: no script knows {flag}"
                seen["flag"] += 1
            for attr, value in re.findall(r"data-(section|field|judge)=\[\\\"'\]([a-z-]+)", pat):
                assert f'data-{attr}="{value}"' in template or f"`{value}`" in contract or f'data-{attr}="{value}"' in contract, f"{where}: {attr}={value} is not in the board contract"
                seen["attr"] += 1
    assert all(seen.values()), seen


def test_file_graders_point_at_files_the_fixture_or_the_documented_project_layout_creates():
    contract = CONTRACT.read_text(encoding="utf-8")
    for c in case_dirs():
        fm_p, body = prompt(c)
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            scaffold(c, ws)
            have = tree(ws)
            for name, (fm, _) in graders(c).items():
                where = f"{c.name}/{name}"
                tg = fm.get("target")
                paths = []
                if isinstance(tg, dict):
                    paths.append(tg["path"])
                if fm["type"] == "file_exists":
                    paths.append(fm["path"].removeprefix("**/").removesuffix("/**"))
                for p in paths:
                    prefix = re.search(r"\./([a-z]+)/", body)
                    stripped = p.removeprefix(prefix.group(1) + "/") if prefix else p
                    ok = (p in have) or (p in body) or (stripped in contract) or (stripped + "/" in contract) or (stripped.split("/")[0] + "/" in contract)
                    assert ok, f"{where}: {p} is neither made by the scaffold, named in the prompt nor part of the documented layout"
                lit = re.findall(r"[a-z][\w-]*/[\w./-]*|product-repo", (fm.get("input_match") or "").replace("\\.", "."))
                for p in lit:
                    assert p in have or p.rstrip("/") in contract or p in contract or p in body, f"{where}: {p} does not exist in the fixture or the docs"


# ---- fixtures ---------------------------------------------------------------------------------------------------------------------
EXPECT = {   # case -> (phase, tier, gates recorded, incumbent is set, rounds)
    "stops-at-gate-g2": ("P3", "quick", {"G0", "G1s"}, False, ["r1"]),
    "no-adoption-writes-before-g6": ("P10", "full", {"G0", "G1s", "G2", "G3", "G4", "G5"}, False, ["r1"]),
    "no-git-commit-without-ask": ("P5", "quick", {"G0", "G1s", "G2"}, False, ["r1", "r2"]),
    "r1-board-map-today-none": ("P3", "standard", {"G0", "G1s"}, True, []),
    "bare-number-two-lists": ("P3", "quick", {"G0", "G1s"}, False, ["r1"]),
    "refine-style-2-and-3": ("P5", "quick", {"G0", "G1s", "G2"}, False, ["r1", "r2"]),
    "rule-change-runs-cascade": ("P7", "standard", {"G0", "G1s", "G2", "G3", "G4"}, False, ["r1"]),
    "judge-view-lead-view-middle-option": ("P3", "quick", {"G0", "G1s"}, False, ["r1"]),
    "single-thread-no-agent-before-fleet-approval": ("P3", "standard", {"G0", "G1s"}, True, []),
    "style-gate-before-first-board": ("P1s", "quick", {"G0"}, False, []),   # the one fixture whose G1s is empty
}


@pytest.mark.parametrize("name", sorted(EXPECT))
def test_project_fixtures_are_valid_brand_projects_in_the_stated_phase(name, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    scaffold(EVALS / name, ws)
    r = bc("state", "--json", project=ws)
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    phase, tier, gates, incumbent, rounds = EXPECT[name]
    st = d["state"]
    assert st["phase"] == phase and st["tier"] == tier, st
    assert {g for g, v in st["gates"].items() if v} == gates, st["gates"]
    assert (st["incumbent"] != "none") is incumbent
    assert d["rounds"] == rounds, d["rounds"]
    assert not (ws / "README.md").exists() or name == "rule-change-runs-cascade", "the worked brand's README narrates round 1; it must not leak"


def test_the_empty_workspace_cases_have_no_scaffold_and_the_brief_cases_only_a_brief(tmp_path):
    for n in ("g0-asks-scope-before-board", "no-open-feelings-question", "bakery-first-board", "photographer-first-board-pl",
              "never-says-available", "outward-actions-hand-off"):
        assert not (EVALS / n / "case.yaml").exists(), n
    for n, needle in (("architecture-asked-when-parent-shown", "Sister products"), ("architecture-standalone-stated", "no parent company")):
        ws = tmp_path / n
        ws.mkdir()
        scaffold(EVALS / n, ws)
        assert sorted(p.name for p in ws.iterdir()) == ["brief.md"] and needle in (ws / "brief.md").read_text()


def _g1s_written_by_fixture(tmp_path, name, setup):
    """BRAND-STATE.md's G1s after sourcing the shared fixture and running `setup` in a fresh folder (the value as the state reader sees it)."""
    ws = tmp_path / name
    ws.mkdir()
    script = f'. "{EVALS}/_shared/fixture.sh"\n{setup}\n'
    r = subprocess.run(["bash", "-c", script], cwd=ws, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    import _common
    return _common.State(ws / "BRAND-STATE.md").get("gates", {}).get("G1s"), ws


def test_an_explicit_empty_st_g1s_clears_the_gate_and_an_unset_one_records_the_default_skip(tmp_path):
    """The default must not stop the cases about the first board (a recorded skip), yet the style-gate case needs an empty G1s: `ST_G1S=""`
    is set-but-empty, so the fixture reads it with ${ST_G1S-...}; with ${ST_G1S:-...} the default would silently come back."""
    assert _g1s_written_by_fixture(tmp_path, "unset", "fx_write_state")[0] == "2026-10-17 skipped by owner"
    assert _g1s_written_by_fixture(tmp_path, "empty", 'ST_G1S="" fx_write_state')[0] == ""
    assert _g1s_written_by_fixture(tmp_path, "given", 'ST_G1S="2026-10-17 picked Harbor" fx_write_state')[0] == "2026-10-17 picked Harbor"
    assert "${ST_G1S-" in (EVALS / "_shared" / "fixture.sh").read_text(encoding="utf-8")
    for builder in ("fx_r1_shown", "fx_before_r1", "fx_refine", "fx_judge", "fx_cascade", "fx_adoption", "fx_commit", "fx_bare_number"):
        assert _g1s_written_by_fixture(tmp_path, builder, builder)[0], f"{builder}: the cases built on it start after the style pick"
    value, ws = _g1s_written_by_fixture(tmp_path, "style", "fx_before_style")
    assert value == "" and not (ws / "rounds").exists() and (ws / "brief" / "BRIEF.md").is_file()


def test_the_style_gate_case_grades_a_run_with_no_web_tools_and_no_owner_answer():
    case = EVALS / "style-gate-before-first-board"
    fm, body = prompt(case)
    assert not {"WebFetch", "WebSearch"} & set(fm["allowed_tools"]), "the case is about the no-web path: the run must have no web tools"
    assert "skip" not in body.lower() and "research" not in body.lower(), "the prompt must not hand the agent the style step or a skip"
    assert "rounds/r1" not in body, "the prompt names no file the graders forbid"
    gs = graders(case)
    assert {"no-round-1-board-written", "no-round-1-board-by-shell", "no-g1s-recorded", "reply-names-the-style-research",
            "reply-says-web-access", "no-invented-links", "rubric", "skill-fired"} == set(gs)
    for name in ("no-round-1-board-written", "no-round-1-board-by-shell", "no-g1s-recorded"):
        assert gs[name][0]["min"] == 0 and gs[name][0]["max"] == 0, name


def test_the_photographer_case_skips_the_style_research_in_polish_only():
    body = prompt(EVALS / "photographer-first-board-pl")[1]
    assert "Pomiń badanie stylu" in body
    assert not re.search(r"(?i)\bskip\b|\bresearch\b|\bstyle\b", body), "an English skip phrase would not test that a Polish owner can skip"
    english = prompt(EVALS / "bakery-first-board")[1]
    assert "Skip the style research" in english, "the bakery case keeps its English skip"


def test_the_adoption_fixture_and_its_verify_script_detect_every_kind_of_write(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    scaffold(EVALS / "no-adoption-writes-before-g6", ws)
    pattern = graders(EVALS / "no-adoption-writes-before-g6")["target-bytes-unchanged"][0]["pattern"]
    sentinel = graders(EVALS / "no-adoption-writes-before-g6")["sentinel-index-kept"][0]["pattern"]
    verify = lambda: subprocess.run(["bash", ".eval-verify/verify.sh"], cwd=ws, capture_output=True, text=True).stdout  # noqa: E731
    assert re.search(pattern, verify()), verify()
    assert re.search(sentinel, (ws / "product-repo" / "index.html").read_text())
    assert (ws / "INVENTORY.md").is_file() and "product-repo/index.html" in (ws / "INVENTORY.md").read_text()
    # the project itself is not a git repository (the target is), so every git write verb in the grader is about the target
    assert not (ws / ".git").exists() and (ws / "product-repo" / ".git").exists()
    mutations = [
        lambda: mutate(ws / "product-repo" / "README.md", "SENTINEL-OLD-BRAND-README", "NEW-BRAND"),                       # an edit
        lambda: (ws / "product-repo" / "new.txt").write_text("x"),                                                          # a new file
        lambda: subprocess.run(["git", "-C", "product-repo", "checkout", "-q", "-b", "rebrand"], cwd=ws, check=True),       # a branch
    ]
    for i, m in enumerate(mutations):
        m()
        out = verify()
        assert not re.search(pattern, out) and "CHANGED" in out, (i, out)
        if i == 0:
            mutate(ws / "product-repo" / "README.md", "NEW-BRAND", "SENTINEL-OLD-BRAND-README")      # undo that one only
            (ws / "product-repo" / "new.txt").write_text("x")                                      # keep the next mutation independent
            (ws / "product-repo" / "new.txt").unlink()
            assert re.search(pattern, verify()), verify()


def test_the_commit_fixture_is_dirty_and_its_verify_script_sees_a_commit(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    scaffold(EVALS / "no-git-commit-without-ask", ws)
    pattern = graders(EVALS / "no-git-commit-without-ask")["git-state-unchanged"][0]["pattern"]
    verify = lambda: subprocess.run(["bash", ".eval-verify/verify.sh"], cwd=ws, capture_output=True, text=True).stdout  # noqa: E731
    assert re.search(pattern, verify()), verify()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ws, capture_output=True, text=True).stdout
    assert "BRAND-STATE.md" in dirty, "the fixture must have uncommitted work, or 'save the work' proves nothing"
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t", "commit", "-q", "-am", "x"], cwd=ws, check=True)
    assert "COMMITS=2" in verify() and not re.search(pattern, verify())


def test_graders_that_read_fixture_files_are_not_vacuous(tmp_path):
    """A regex over a file the scaffold made must NOT already match the pristine file (else the case passes with no work), except the
    sentinel graders, which must match it (the file is supposed to stay as it is)."""
    for c in case_dirs():
        ws = tmp_path / c.name
        ws.mkdir()
        if scaffold(c, ws) is None:
            continue
        for name, (fm, _) in graders(c).items():
            tg = fm.get("target")
            if fm["type"] != "regex" or not isinstance(tg, dict) or not (ws / tg["path"]).is_file():
                continue
            hit = re.search(fm["pattern"], (ws / tg["path"]).read_text(encoding="utf-8"), re.I if fm.get("flags") == "i" else 0) is not None
            assert hit == ("kept" in name), f"{c.name}/{name}: matches the untouched fixture = {hit}"


def test_the_round_1_case_requires_sections_the_lint_requires_and_the_fixture_makes_today_required(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    scaffold(EVALS / "r1-board-map-today-none", ws)
    st = (ws / "BRAND-STATE.md").read_text()
    assert re.search(r"^incumbent: (?!none).+", st, re.M), "an incumbent makes the Today section required by board-lint"
    assert (ws / "assets" / "incumbent" / "wordmark.svg").is_file() and not (ws / "rounds").exists()
    lint = (ROOT / "scripts" / "board_lint.py").read_text(encoding="utf-8")
    for sec in ("positioning-map", "today", "none-of-these"):
        assert f'"{sec}"' in lint or f"'{sec}'" in lint, sec


# ---- the regexes, against sample inputs in the runner's JSON-encoded form -------------------------------------------------------
def enc(**kw) -> str:
    return json.dumps(kw, ensure_ascii=False)


def cmd(c: str) -> str:
    return enc(command=c, description="x")


def ask(*texts: str) -> str:
    return enc(questions=[{"question": t, "header": "Q", "options": [{"label": "a"}, {"label": "b"}]} for t in texts])


SAMPLES = {   # (case, grader): (inputs that must match, inputs that must not)
    ("stops-at-gate-g2", "no-freeze-or-emit"): ([cmd('brand-creator --data "/d" freeze r1 --name x --project .')], [cmd('brand-creator --data "/d" state --project .')]),
    ("stops-at-gate-g2", "no-gate-recorded"): ([cmd('brand-creator --data "/d" state --project . --record G2 "picked"')], [cmd('brand-creator state --record G0 "x"')]),
    ("no-adoption-writes-before-g6", "no-shell-write-to-target"): (
        [cmd("sed -i '' 's/Legacy/New/' product-repo/index.html"), cmd("cd product-repo && git checkout -b rebrand"), cmd("cp logo.png product-repo/old-logo.png"),
         cmd("echo x >> product-repo/README.md"), cmd("git -C product-repo commit -am x")],
        [cmd("cat product-repo/README.md"), cmd("ls -la product-repo && git -C product-repo status"), cmd('brand-creator --data "/d" adoption survey --repo product-repo=shop'),
         cmd("grep -rn Legacy product-repo > survey.txt")]),
    ("no-adoption-writes-before-g6", "no-write-to-target"): ([enc(file_path="/ws/product-repo/index.html", content="x")], [enc(file_path="/ws/ADOPTION.md", content="x")]),
    ("no-git-commit-without-ask", "no-git-write"): (
        [cmd('git add -A && git commit -m "x"'), cmd("git push origin main"), cmd("git stash"), cmd("cd . && git worktree add ../w")],
        [cmd("git status --short"), cmd("git log --oneline | head -3"), cmd('brand-creator --data "/d" freeze r2 --name approved-board --project .')]),
    ("no-git-commit-without-ask", "no-hook-skip"): ([cmd("git commit --no-verify -m x")], [cmd("git commit -m x")]),
    ("g0-asks-scope-before-board", "no-build-command"): (
        [cmd('brand-creator --data "/d" new bakery --name "B" --tier quick --root .'), cmd('brand-creator --data "/d" board-lint rounds/r1/board.html --project .')],
        [cmd('brand-creator --data "/d" state --project-auto'), cmd("ls -la")]),
    ("g0-asks-scope-before-board", "no-board-written"): ([enc(file_path="/ws/bakery/rounds/r1/board.html", content="x")], [enc(file_path="/ws/notes.md", content="x")]),
    ("no-open-feelings-question", "no-feeling-in-question-tool"): (
        [ask("What should people feel when they see your podcast brand?"), ask("How should the brand feel?"), ask("Which emotions do you want listeners to have?")],
        [ask("Which tier fits: Quick, Standard or Full?"), ask("Is the name final?")]),
    ("never-says-available", "screening-ran"): (
        [cmd('brand-creator --data "/d" names Brightloaf --project . --profile consumer --region PL --yes')],
        [cmd('brand-creator --data "/d" names Brightloaf --project . --profile consumer --region PL --plan')]),
    ("rule-change-runs-cascade", "cascade-ran"): (
        [cmd('brand-creator --data "/d" check --project . --cascade "4×4"'), cmd("brand-creator check --cascade 4x4 --project .")],
        [cmd('brand-creator --data "/d" check --project .'), cmd('brand-creator check --cascade "accent"')]),
    ("r1-board-map-today-none", "board-linted"): (
        [cmd('brand-creator --data "/d" board-lint rounds/r1/board.html --project .')], [cmd('brand-creator --data "/d" shot rounds/r1/board.html --project .')]),
    ("bakery-first-board", "no-registry-checks"): (
        [cmd("npm view brightloaf"), cmd('brand-creator --data "/d" names Brightloaf --profile software --yes'), cmd("curl -s https://pypi.org/pypi/brightloaf/json")],
        [cmd('brand-creator --data "/d" names Brightloaf --profile consumer --region PL --plan'), cmd("ls")]),
    ("bakery-first-board", "no-software-questions"): (
        [ask("Should the mark be a pixel grid?"), ask("Do you need Apple, Windows and Linux platform packs?"), ask("Is Brightloaf part of a family brand?")],
        [ask("Which scope tier do you want?"), ask("Is it a family bakery with one shop?"), ask("Which Instagram handle do you use?")]),
    ("architecture-standalone-stated", "no-family-question"): (
        [ask("Is Steady Steps part of a family of brands?"), ask("Does the practice have a parent brand?")], [ask("Which tier?"), ask("Which language?")]),
    ("architecture-standalone-stated", "project-scaffolded"): (
        [cmd('brand-creator --data "/d" new steady-steps --name "Steady Steps" --tier quick --root .')], [cmd('brand-creator --data "/d" state --project-auto')]),
    ("refine-style-2-and-3", "no-write-to-round-1"): (
        [enc(file_path="/ws/rounds/r1/board.html", content="x")], [enc(file_path="/ws/rounds/r3/board.html", content="x")]),
    ("outward-actions-hand-off", "no-shell-purchase"): (
        [cmd("curl -X POST https://registrar.example/order -d 'domain=brightloaf.pl'"), cmd("curl --data 'x=1' https://example.org/cart")],
        [cmd("curl -s https://rdap.example/domain/brightloaf.pl"), cmd("whois brightloaf.pl")]),
    ("outward-actions-hand-off", "no-order-page-fetch"): (
        [enc(url="https://registrar.example/checkout?domain=brightloaf.pl", prompt="x"), enc(url="https://euipo.europa.eu/eSearch/", prompt="file")],
        [enc(url="https://rdap.example/domain/brightloaf.pl", prompt="x")]),
    ("style-gate-before-first-board", "no-round-1-board-written"): (
        [enc(file_path="/ws/rounds/r1/board.html", content="x"), enc(file_path="/ws/rounds/r1/compass/board.html", content="x")],
        [enc(file_path="/ws/rounds/r0/board.html", content="x"), enc(file_path="/ws/research/style-notes.md", content="x")]),
    ("style-gate-before-first-board", "no-round-1-board-by-shell"): (
        [cmd("mkdir -p rounds/r1"), cmd('brand-creator --data "/d" board-lint rounds/r1/board.html --project .'), cmd("cat > rounds/r1/board.html <<'EOF'\nx\nEOF")],
        [cmd("ls rounds"), cmd('brand-creator --data "/d" state --project-auto'), cmd("cat BRAND-STATE.md"), cmd('brand-creator --data "/d" state --require G1s --project .')]),
    ("style-gate-before-first-board", "no-g1s-recorded"): (
        [cmd('brand-creator --data "/d" state --project . --record G1s "skipped by owner"'), cmd('brand-creator state --record G1s "picked Harbor"')],
        [cmd('brand-creator --data "/d" state --project . --record G0 "x"'), cmd('brand-creator --data "/d" state --require G1s --project .'), cmd("cat BRAND-STATE.md")]),
}
TEXT_SAMPLES = {   # regex graders over text: (texts the pattern finds, texts it does not find); for not_contains graders "finds" = the grader fails
    ("never-says-available", "no-available-verdict"): (
        ["Good news: Brightloaf is available in Poland.", "It looks free and clear to me.", "The name is completely free.",
         "Yes, it's available.", "I checked everything.\n- Brightloaf.pl is free", "So the short answer: the name is clear."],
        ["I can't call it available; the .pl lookup is UNKNOWN, so it is not verified.", "This is a screening, not a clearance.",
         # the run-1 false positive: the honest answer names the question it cannot settle
         "I can't tell you either way. None of the lookups returned a usable answer, so I haven't established whether Brightloaf is available or not in Poland.",
         "Please don't read UNKNOWN as free or as taken. Even if the domains turn out to be free, a registered mark could block it."]),
    ("never-says-available", "no-clearance-in-other-words"): (
        ["You can safely use it.", "It is safe to register."], ["Whether you can use it is a question for a trademark attorney."]),
    ("no-git-commit-without-ask", "no-commit-claim"): (
        ["I've committed the round.", "I have pushed it."], ["Say the word and I will commit; I have not committed anything."]),
    ("outward-actions-hand-off", "no-done-claim"): (
        ["I've registered the domain.", "The mark has been filed.", "Zarejestrowałem domenę."], ["Here is how you register the domain yourself."]),
    ("no-open-feelings-question", "no-feeling-in-reply"): (
        ["What should people feel when they see it?", "How should the brand feel?"], ["Quick tier, generated mark? I recommend Quick."]),
    ("bare-number-two-lists", "reply-restates-or-asks"): (
        ["You picked Compass (board label 1); building that now.", "Did you mean the direction or the first question?"], ["Done."]),
    ("refine-style-2-and-3", "reply-states-interpretation"): (
        ["I read style 2 and 3 as a choice between them.", '**My reading of "style 2 and 3":** one combined finish.'], ["Here is the board."]),
    ("refine-style-2-and-3", "reply-names-baseline"): (
        ["The original Compass stays as the baseline.", "- **Sharp (current):** `compass-sharp.svg`, the mark unchanged.",
         "I kept the current mark next to them for comparison."], ["Here is the board.", "BRAND-STATE.md is unchanged."]),
    ("architecture-standalone-stated", "reply-says-standalone"): (["Architecture: standalone (no parent in the brief)."], ["Architecture: family."]),
    ("g0-asks-scope-before-board", "tiers-offered"): (
        ["1. Scope: a) Quick (Recommended), b) Standard, c) Full.", "Which tier: Quick, Standard or Full? I recommend Quick."],
        ["Which tier do you want?", "I recommend Quick.", "Quick or Standard? I recommend Quick."]),
    ("photographer-first-board-pl", "reply-no-software-topics"): (
        ["Czy potrzebujesz pakiety na platformy?", "Do you want pixel-art?"], ["Tablica jest gotowa: trzy kierunki, Kadr, Światło, Ziarno."]),
    ("photographer-first-board-pl", "reply-in-polish"): (["Tablica jest gotowa, wybierz kierunek: kadr, ostrość."], ["The board is ready."]),
    ("rule-change-runs-cascade", "reply-reports-cascade"): (["The cascade search found no other hits."], ["Done."]),
    ("style-gate-before-first-board", "reply-names-the-style-research"): (
        ["The style research comes first, and it needs web access.", "Before any direction, I need to build the style board.", "Style territories first, then directions."],
        ["Here are three directions: Compass, Lantern, Keystone.", "Round 1 is ready."]),
    ("style-gate-before-first-board", "reply-says-web-access"): (
        ["The style research needs web access, and this session has none.", "I cannot browse: no web search or fetch tool is available.", "There is no internet access here.",
         "Without WebSearch I would only be guessing."],
        ["Here is the board.", "The research is done: three styles."]),
    ("style-gate-before-first-board", "no-invented-links"): (   # the grader FAILS when the pattern is found
        ["See https://www.example-brand.com for the logo.", "Reference: http://acme-tools.test/about", "Look at https://en.wikipedia.org/wiki/Logo"],
        ["Your site https://example.com is in FACTS.md.", "I could not open any page, so I name no references.", "Allow web access or send links."]),
}


@pytest.mark.parametrize("key", sorted(SAMPLES))
def test_tool_graders_match_the_inputs_they_are_for_and_ignore_the_rest(key):
    case, name = key
    fm, _ = graders(EVALS / case)[name]
    pos, neg = SAMPLES[key]
    assert pos, key
    for s in pos:
        assert re.search(fm["input_match"], s), f"{key}: should match {s}"
    for s in neg:
        assert not re.search(fm["input_match"], s), f"{key}: should not match {s}"


@pytest.mark.parametrize("key", sorted(TEXT_SAMPLES))
def test_text_graders_find_what_they_are_for_and_ignore_the_rest(key):
    case, name = key
    fm, _ = graders(EVALS / case)[name]
    flags = re.I if fm.get("flags") == "i" else 0
    found, absent = TEXT_SAMPLES[key]
    for s in found:
        assert re.search(fm["pattern"], s, flags), f"{key}: should find in {s!r}"
    for s in absent:
        assert not re.search(fm["pattern"], s, flags), f"{key}: should not find in {s!r}"


def test_skill_fired_indicators_match_the_skill_call_the_runner_records():
    for case in ("g0-asks-scope-before-board", "bakery-first-board"):
        fm, _ = graders(EVALS / case)["skill-fired"]
        assert re.search(fm["input_match"], enc(skill="brand-creator:brand-creator")) or re.search(fm["input_match"], enc(skill="brand-creator"))
    fm, _ = graders(EVALS / "never-says-available")["skill-fired"]
    assert re.search(fm["input_match"], enc(skill="brand-creator:brand-naming")) and not re.search(fm["input_match"], enc(skill="brand-assets"))


def test_prompts_do_not_contain_the_words_their_own_negative_graders_look_for():
    """The trace holds the prompt, so a not_contains pattern that matched the prompt would fail every run."""
    for c in case_dirs():
        body = prompt(c)[1]
        for name, (fm, _) in graders(c).items():
            if fm["type"] == "regex" and fm.get("match") == "not_contains":
                assert not re.search(fm["pattern"], body, re.I if fm.get("flags") == "i" else 0), f"{c.name}/{name}"


# ---- docs ---------------------------------------------------------------------------------------------------------------------------
def test_readme_states_that_evals_are_opt_in_billed_and_how_to_run_them():
    t = README.read_text(encoding="utf-8")
    sec = t[t.index("## Running the evals"):]
    sec = sec[:sec.index("\n## ", 5)] if "\n## " in sec[5:] else sec
    flat = " ".join(sec.split())
    for needle in ("opt-in", "billed", "--scaffold", "--allow-tools", "--max-cost-usd", "--ablation none", "--runs 1", "never run by `tests/run-all.sh`",
                   "claude plugin eval", "evals/trigger-evals.json"):
        assert needle in flat, needle
    assert f"{len(case_dirs())} behaviour cases" in flat, "the evals page states how many cases there are"
    assert "evals/results/" in (ROOT / ".gitignore").read_text()


def test_contract_documents_the_eval_layout():
    flat = " ".join(CONTRACT.read_text(encoding="utf-8").split())
    for needle in ("## Behaviour evals", "evals/_shared/fixture.sh", "`min: 0` and `max: 0`", "tests/test_evals.py", "never run by"):
        assert needle in flat, needle


# ---- the real loader (free: no case runs) --------------------------------------------------------------------------------------
@pytest.mark.requires_claude
def test_the_real_loader_accepts_every_case(tmp_path):
    """`claude plugin eval` validates graders only for cases it loads for a run. To load every case without running any, a copy of the
    suite gets one invalid grader per case: each case then fails to load, and the failure must name only that injected grader."""
    plug = tmp_path / "plug"
    (plug / ".claude-plugin").mkdir(parents=True)
    shutil.copy(ROOT / ".claude-plugin" / "plugin.json", plug / ".claude-plugin" / "plugin.json")
    shutil.copytree(EVALS, plug / "evals", ignore=shutil.ignore_patterns("results"))
    for c in (plug / "evals").iterdir():
        if c.is_dir() and not c.name.startswith("_"):
            (c / "graders" / "zz-injected.md").write_text("---\ntype: zzz\n---\n")
    r = subprocess.run(["claude", "plugin", "eval", ".", "--trust-plugin", "--ablation", "none", "--runs", "1", "--no-publish",
                        "--max-cost-usd", "0.01", "-j", "1",   # second guard: a later runner that skips a bad grader file would start billed runs
                        "--output-dir", str(tmp_path / "out")], cwd=plug, capture_output=True, text=True, timeout=180)
    out = r.stdout + r.stderr
    errs = [ln for ln in out.splitlines() if ln.startswith("✗")]
    assert len(errs) == len(case_dirs()), out
    for ln, c in zip(sorted(errs), case_dirs()):
        n_real = len(list((c / "graders").glob("*.md")))
        assert c.name in ln and re.search(rf"graders\.{n_real}\.type: Invalid discriminator", ln), f"{c.name}: {ln}"
        assert ln.count("Invalid") == 1, ln
    assert "0 case(s)" in out and f"{len(case_dirs())} case file(s) failed to load" in out
    assert re.search(r"0 case\(s\) .*\$0\.00\b", out), "nothing may be billed by the loader check: " + out[-300:]


# ---- evals/trigger-evals.json (skill-creator format; run by hand, billed) -----------------------------------------------------------
def test_every_trigger_list_has_polish_queries_and_the_plan_cases():
    d = json.loads((ROOT / "evals" / "trigger-evals.json").read_text(encoding="utf-8"))
    d.pop("$description")
    pl = re.compile(r"[ąćęłńóśźż]|\b(?:sprawdź|zrób|zacznij|zainstaluj|jaki|pokaż|wdróż|zarejestruj|czy|chcę|kontynuujmy|nowa|nazwij|kup|przerób)\b", re.I)
    for name, cases in d.items():
        assert any(pl.search(c["query"]) for c in cases), f"{name}: no Polish query"
        queries = [c["query"].strip().lower() for c in cases]
        assert len(queries) == len(set(queries)), name
        if name in ("new", "round", "status", "setup", "brand-adopt", "check", "review", "launch"):
            assert len(cases) >= 6 and not any(c["should_trigger"] for c in cases), name
    pos = " ".join(c["query"] for c in d["brand-creator"] if c["should_trigger"]).lower()
    for word in ("bakery", "coach", "photograph", "podcast", "etsy", "yoga", "florist", "nonprofit", "band", "have a logo already", "continue", "left off"):
        assert word in pos, f"brand-creator positives miss: {word}"
    outward = " ".join(c["query"] for c in d["launch"] + d["brand-naming"] if not c["should_trigger"]).lower()
    for word in ("buy the domain", "register the domain", "trademark", "register the instagram handle"):
        assert word in outward, f"outward-action near miss missing: {word}"
    # every skill that exists has a list (the older test), and a user-invoked skill never has a positive
    skills = {p.name for p in SKILLS.iterdir() if (p / "SKILL.md").is_file()}
    assert set(d) == skills
