"""Static checks over agents/*.md and workflows/*.js (the dry runs live in tests/node/workflows.test.mjs)."""
import re

from helpers import ROOT, bc

AGENTS = ROOT / "agents"
WORKFLOWS = ROOT / "workflows"
ORCH = ROOT / "skills" / "brand-creator" / "SKILL.md"
FRAG = ROOT / "skills" / "brand-creator" / "references" / "prompt-fragments.md"
FLEET = ROOT / "skills" / "brand-creator" / "references" / "fleet.md"
PREFIX = "Only for brand-creator workflows or an approved fleet; do not auto-delegate."
SUPPORTED = {"name", "description", "model", "effort", "maxTurns", "autoCompactWindow", "tools", "disallowedTools", "skills",
             "memory", "background", "omitClaudeMd", "color"}           # plugin agents; isolation is supported but never wanted here
IGNORED = {"permissionMode", "hooks", "mcpServers", "initialPrompt", "isolation"}
PLAN = {  # plan-v2 agents/ row: tier and tools
    "brand-designer": ("opus", {"Read", "Write", "Edit", "Glob", "Grep", "Bash"}),
    "brand-judge": ("opus", {"Read", "Grep", "Glob"}),
    "brand-reviewer": ("opus", {"Read", "Grep", "Glob", "Bash"}),
    "brand-researcher": ("sonnet", {"Read", "Grep", "Glob", "WebSearch", "WebFetch", "Bash"}),
    "brand-inventory": ("sonnet", {"Read", "Grep", "Glob"}),
    "brand-namer": ("sonnet", {"Read", "Grep", "Glob", "Bash"}),   # review R6-4: no web tools
    "brand-implementer": ("sonnet", {"Read", "Write", "Edit", "Glob", "Grep", "Bash"}),
}


def agent(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name}: frontmatter must start on line 1"
    end = text.index("\n---\n", 4)
    fm = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z][A-Za-z0-9]*):\s*(.+)$", line)
        assert m, f"{path.name}: one-line key: value frontmatter only ({line!r})"
        assert m.group(1) not in fm, f"{path.name}: duplicate key {m.group(1)}"
        # plain YAML scalars: a ": " or " #" inside, or a leading indicator, would make the frontmatter fail to parse,
        # and a plugin agent whose frontmatter does not parse loads with every field ignored (no tools allowlist, no model)
        v = m.group(2).strip()
        assert ": " not in v and " #" not in v and not re.match(r"[\[\]{}&*!|>'\"%@`,?:-]", v), f"{path.name}: {m.group(1)} is not a plain YAML scalar"
        fm[m.group(1)] = m.group(2).strip()
    return fm, text[end + 5:]


def rules_line():
    lines = [ln for ln in ORCH.read_text(encoding="utf-8").splitlines() if ln.startswith("RULES: ")]
    assert len(lines) == 1
    return lines[0]


def test_every_planned_agent_exists_with_its_tier_tools_and_turn_limit():
    files = sorted(p.stem for p in AGENTS.glob("*.md"))
    assert files == sorted(PLAN)
    for name, (tier, tools) in PLAN.items():
        fm, body = agent(AGENTS / f"{name}.md")
        assert fm["name"] == name
        assert set(fm) <= SUPPORTED and not set(fm) & IGNORED, (name, set(fm) - SUPPORTED)
        assert fm["model"] == tier, name
        got = {t.strip() for t in fm["tools"].split(",")}
        assert got == tools, (name, got ^ tools)
        assert "Agent" not in got and "Task" not in got, f"{name}: no recursive fan-out"
        assert re.fullmatch(r"[1-9][0-9]{1,2}", fm["maxTurns"]) and int(fm["maxTurns"]) <= 150, name   # a ceiling, not a target
        assert fm["description"].startswith(PREFIX), name
        assert "-tier" not in fm["description"], f"{name}: the tier lives in the model field, not the description"
        assert len(fm["description"]) <= 1024
        assert "${CLAUDE_PLUGIN_ROOT}" not in body and "${CLAUDE_PLUGIN_DATA}" not in body, f"{name}: paths come in the prompt"
    # the read-only agents really cannot write
    for name in ("brand-judge", "brand-inventory"):
        assert PLAN[name][1].isdisjoint({"Write", "Edit", "Bash", "NotebookEdit"})
    assert PLAN["brand-reviewer"][1].isdisjoint({"Write", "Edit", "NotebookEdit"})


def test_every_agent_body_carries_the_rules_line_verbatim():
    want = rules_line()
    for p in AGENTS.glob("*.md"):
        _, body = agent(p)
        assert body.splitlines().count(want) == 1, p.name


def test_the_designer_carries_the_test_line_verbatim_and_each_agent_its_method():
    test_line = [ln for ln in FRAG.read_text(encoding="utf-8").splitlines() if ln.startswith("TEST: ")]
    assert len(test_line) == 1 and "Read every tile, iterate at least twice" in test_line[0]
    _, d = agent(AGENTS / "brand-designer.md")
    assert test_line[0] in d.splitlines()
    assert "16 px first" in d and "only place you write" in d and "snapshot verify" in d
    _, j = agent(AGENTS / "brand-judge.md")
    for needle in ("what you would graft", "MUST-FIX", "if something is fine, say so", "the owner decides", "screening, not clearance"):
        assert needle in j, needle
    _, r = agent(AGENTS / "brand-reviewer.md")
    for needle in ("done, partly done or not done", "at least six pairs", "`cmp` every file", "Decisions for you",
                   "if something is fine, say so", "say why instead of marking it done", "still copy"):
        assert needle in r, needle
    _, s = agent(AGENTS / "brand-researcher.md")
    for needle in ('"claims"', '"tier": "primary|secondary|UNVERIFIED"', "open_questions", "Read only: do not register",
                   "privacy OK", "--plan"):
        assert needle in s, needle
    _, n = agent(AGENTS / "brand-namer.md")
    for needle in ("no web search and no web fetch tool", "Never run `--yes`", "--plan", "Names stay on this machine", "screening, not clearance"):
        assert needle in n, needle
    _, r2 = agent(AGENTS / "brand-reviewer.md")
    assert "you have no web tools" in r2 and "`brand-researcher` call" in r2          # R6-3: the reviewer cannot re-fetch
    fleet = FLEET.read_text(encoding="utf-8")
    assert "refuting verifier" in fleet and "`brand-reviewer` has no web tools" in fleet
    assert "brand-reviewer` that re-fetches" not in fleet
    _, i = agent(AGENTS / "brand-inventory.md")
    assert "templates/INVENTORY.md" in i and "platform-specs.json" in i and "UNVERIFIED" in i
    _, m = agent(AGENTS / "brand-implementer.md")
    for needle in ("find\n   each spot by its content", "report it as not done", "Never pass `--no-verify`",
                   "Do not commit, merge, push, stash", "do not start over blindly"):
        assert needle in m, needle


def _code(text):
    return re.sub(r"^\s*//.*$", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S), flags=re.M)


def test_workflows_follow_the_runtime_rules():
    want = rules_line()
    files = sorted(WORKFLOWS.glob("*.js"))
    assert [p.stem for p in files] == ["adopt", "directions", "naming", "review-panel"]
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert text.startswith("export const meta = {\n"), p.name
        assert re.search(rf"^  name: '{p.stem}',$", text, re.M), p.name
        code = _code(text)
        for bad in (r"\bDate\.now\b", r"\bMath\.random\b", r"new Date\(\s*\)", r"\bimport\s*\(", r"\brequire\s*\(", r"isolation\s*:"):
            assert not re.search(bad, code), (p.name, bad)
        assert f"const RULES = '{want}'" in text, p.name
        assert "agentType: 'brand-creator:' + type" in text, p.name
        tiers = re.search(r"const AGENT_TIER = \{([^}]*)\}", text).group(1)
        for name, tier in re.findall(r"'(brand-[a-z]+)': '([a-z]+)'", tiers):
            assert PLAN[name][0] == tier, (p.name, name)
        assert ".filter(Boolean)" in code and "RESUME NOTES:" in text, p.name
        assert "approved_agents" in code and "ceiling" in code, p.name
        assert re.search(r"Agents in the default path: .*", text), f"{p.name}: the header documents its agent count"


def test_fleet_plan_check_passes_on_the_shipped_files():
    r = bc("fleet-plan", "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS: 7 agents, 4 workflows checked" in r.stdout


def test_the_fleet_gate_and_refine_loop_are_documented_where_they_are_used():
    orch = ORCH.read_text(encoding="utf-8")
    sec = orch[orch.index("## Fleets and workflows (opt-in, after the fleet gate)"):]
    for needle in ("Single-thread stays the default", "fleet-plan", "agent count", "models that will actually run",
                   "session model is the ceiling", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE", "size guideline", "rough",
                   "explicit yes", "approved_agents", "one `brand-creator:brand-reviewer` call"):
        assert needle in sec, needle
    fleet = FLEET.read_text(encoding="utf-8")
    for w in ("`directions`", "`review-panel`", "`naming`", "`adopt`"):
        assert w in fleet
    for needle in ("## The refine loop (main thread, one reviewer call)", "Wait for an explicit yes", "single-thread is the default",
                   "No recursive fan-out", "never edit the files it owns", "rough cost"):
        assert needle in fleet, needle
    refine = (ROOT / "skills/brand-creator/references/phases/05-refinement.md").read_text(encoding="utf-8")
    assert "## Refine loop with one reviewer call" in refine and "Refinement is never a workflow" in refine
    for skill, wf in (("review", "review-panel"), ("brand-adopt", "adopt"), ("brand-naming", "naming")):
        t = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert f"fleet-plan {wf}" in t and "fleet.md" in t, skill
    page = (ROOT / "docs/manual/reference/agents-and-workflows.md").read_text(encoding="utf-8")
    assert "## The four workflows" in page and "fleet" in (ROOT / "docs/manual/reference/costs.md").read_text(encoding="utf-8")
    assert "## Agents and workflows" in (ROOT / "scripts/CONTRACT.md").read_text(encoding="utf-8")


def test_directions_needs_the_style_pick_and_the_fleet_reference_says_so():
    """Nothing is drawn before G1s: the script refuses to start without args.g1s (the dry runs are in tests/node/workflows.test.mjs),
    and the argument is documented where the other arguments are."""
    js = (WORKFLOWS / "directions.js").read_text(encoding="utf-8")
    assert re.search(r"if \(!String\(A\.g1s \|\| ''\)\.trim\(\)\) fail\('args\.g1s must carry the G1s record from BRAND-STATE\.md", js)
    assert js.index("A.g1s || ''") < js.index("A.directions"), "the check comes before any direction is read"
    fleet = FLEET.read_text(encoding="utf-8")
    sec = fleet[fleet.index("## Arguments every workflow needs"):fleet.index("## Models: the session model is a ceiling")]
    bullet = " ".join(sec[sec.index("- `directions`:"):sec.index("- `review-panel`:")].split())
    for needle in ("`g1s` (required", "the G1s record", "style board", "rounds/r0/board.html", "skipped by owner", "n/a: round 1 drawn before the style step",
                   "refuses to start without it", "as `adopt` does without `g6`"):
        assert needle in bullet, needle
    assert "needs the style pick (G1s) first" in fleet and "Nor is the style research (P1s)" in " ".join(fleet.split())
    orch = ORCH.read_text(encoding="utf-8")
    assert "`g1s`" in orch[orch.index("## Fleets and workflows"):], "SKILL.md tells the lead that directions takes the G1s record"
