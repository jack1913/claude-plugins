"""Static checks over the skills and their references: frontmatter, budgets, links, verbatim lines, wrappers."""
import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess

from helpers import ROOT

SKILLS = ROOT / "skills"
ORCH = SKILLS / "brand-creator" / "SKILL.md"
REFS = SKILLS / "brand-creator" / "references"
WRAPPERS = ("new", "round", "status", "setup", "check", "review", "launch")
ENTRY = 'brand-creator --data "${CLAUDE_PLUGIN_DATA}"'  # quoted: a data path may hold spaces (CONTRACT.md, entry point)
RULE = "Bash(brand-creator *)"


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path}: frontmatter must start on line 1"
    end = text.index("\n---\n", 4)
    fm = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([a-z][a-z_-]*):\s*(.*)$", line)
        assert m, f"{path}: frontmatter lines must be single-line key: value ({line!r})"
        v = m.group(2).strip()
        if len(v) >= 2 and v[0] == v[-1] == '"':
            v = v[1:-1]
        fm[m.group(1)] = v
    return fm, text[end + 5:]


def all_skills():
    return sorted(p for p in SKILLS.glob("*/SKILL.md"))


def test_every_skill_has_valid_frontmatter():
    allowed = {"name", "description", "when_to_use", "argument-hint", "arguments", "disable-model-invocation",
               "allowed-tools", "compatibility", "license", "metadata"}
    names = set()
    for p in all_skills():
        fm, body = frontmatter(p)
        assert set(fm) <= allowed, (p, set(fm) - allowed)
        assert fm["name"] == p.parent.name and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fm["name"]) and len(fm["name"]) <= 64
        assert "claude" not in fm["name"] and "anthropic" not in fm["name"]
        assert fm["description"] and len(fm["description"]) <= 1024, p
        assert len(fm["description"]) + len(fm.get("when_to_use", "")) <= 1536, p
        assert not re.match(r"(?i)(i|we|you)\b", fm["description"]), f"{p}: description must be third person"
        assert len(body.splitlines()) < 500, p
        names.add(fm["name"])
    assert {"brand-creator", "brand-naming", "brand-assets", "brand-book", "brand-adopt", *WRAPPERS} <= names


def yaml_plain_scalar_problem(v):
    """Why an unquoted YAML value would not load as one string (Claude Code parses frontmatter as YAML), or None."""
    if not v or (len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'"):
        return None
    if v[0] in "[]{}>|*&!%@`#,?-\"'" and not re.match(r"-[^\s-]", v):
        return f"starts with {v[0]!r}"
    if ": " in v or v.endswith(":"):
        return "holds ': ' (a mapping inside the value)"
    if " #" in v:
        return "holds ' #' (the rest is a comment)"
    return None


def test_every_frontmatter_value_is_valid_yaml():
    """The line parser above is lenient; a value with ': ' in it fails a real YAML loader (it did, for launch and four
    descriptions), and the skill or agent then loads without its description."""
    bad = []
    for p in [*all_skills(), *sorted((ROOT / "agents").glob("*.md"))]:
        text = p.read_text(encoding="utf-8")
        end = text.index("\n---\n", 4)
        for line in text[4:end].splitlines():
            m = re.match(r"^([A-Za-z][A-Za-z_-]*):\s*(.*)$", line)
            if m and (why := yaml_plain_scalar_problem(m.group(2).strip())):
                bad.append(f"{p.relative_to(ROOT)}: {m.group(1)} {why}")
    assert not bad, "\n".join(bad)


def test_the_yaml_value_check_catches_what_a_loader_rejects():
    assert yaml_plain_scalar_problem("Writes the list (LAUNCH.md: trademark first)")
    assert yaml_plain_scalar_problem("ends here: ")
    assert yaml_plain_scalar_problem("a value # and a comment")
    assert yaml_plain_scalar_problem("[--name <x>]")
    assert yaml_plain_scalar_problem('"[--name <x>]"') is None
    assert yaml_plain_scalar_problem("Bash(brand-creator *)") is None
    assert yaml_plain_scalar_problem("plain text, with commas (and brackets)") is None


def test_orchestrator_frontmatter():
    fm, _ = frontmatter(ORCH)
    assert "disable-model-invocation" not in fm  # the one model-invocable skill in this stage
    assert fm["description"].startswith("Starts or continues a brand-identity project")
    assert "not for building web pages" in fm["description"]
    for trig in ("księga znaku", "identyfikacja wizualna", "zaprojektuj logo", "nowa marka", "rebranding", "logo dla firmy",
                 "BRAND-STATE.md", "buy the domain", "file the trademark", "fold in a judge report", "accent minimum", "Etsy",
                 "shop", "podcast", "brand guidelines", "brand book"):
        assert trig in fm["when_to_use"], trig
    # headroom: the skill listing cuts the text at 1536 characters; keep at least 150 spare so a later addition does not cut the
    # Polish triggers at the end
    assert len(fm["description"]) + len(fm["when_to_use"]) <= 1536 - 150, len(fm["description"]) + len(fm["when_to_use"])
    assert fm["compatibility"] and len(fm["compatibility"]) <= 500 and "Claude Code" in fm["compatibility"]
    assert fm["allowed-tools"] == RULE


def test_orchestrator_top_holds_the_core_within_the_compaction_budget():
    text = ORCH.read_text(encoding="utf-8")
    top = text[: text.index("## Round mechanics")]
    assert len(top) <= 20000, f"top section is {len(top)} characters (about {len(top) // 4} tokens); keep it under ~5k tokens"
    needles = ["Re-invoke this skill after compaction", "## Step 0", "state --project-auto", "projects_root", " new <slug>",
               "## Scope tiers", "Quick", "Standard", "Full", "## Phase map", "**G0 Scope.**", "**G1 Name go.**",
               "**G2 Direction pick.**", "**G2b-a Reset", "**G2b-b Recover", "**G3 Refined approval.**", "**G4 System rules.**",
               "**G-sys tripwire.**", "**G5 Pack and book.**", "**G6 Adoption.**", "**G7 Outward.**", "**Cascade (always on).**",
               "**Fleet gate.**", "## Response template", "## Working style", "## Review surface", "**Mark source**",
               "**Architecture**", "generated", "authored-vector", "existing", "standalone", "family-member", "product-in-family"]
    for n in needles:
        assert n in top, n
    for ph in range(14):
        assert f"| P{ph} |" in top, f"P{ph} missing from the phase map"


def rules_line(text):
    lines = [ln for ln in text.splitlines() if ln.startswith("RULES: ")]
    assert len(lines) == 1, lines
    return lines[0]


def test_rules_line_is_verbatim_everywhere():
    want = rules_line(ORCH.read_text(encoding="utf-8"))
    for frag in ("never rm/pkill", "never commit/push/merge/stash/worktree unless explicitly asked", "no outward actions",
                 "raise errors explicitly, no silent fallbacks", "read your shots before any visual claim",
                 "never edit adoption targets before G6"):
        assert frag in want
    assert rules_line((REFS / "prompt-fragments.md").read_text(encoding="utf-8")) == want
    tests_line = [ln for ln in (REFS / "prompt-fragments.md").read_text().splitlines() if ln.startswith("TEST: ")]
    assert tests_line == ["TEST: screenshot 1440×900 light+dark and 390×844, Read every tile, iterate at least twice; print one-line check (overflow, errors, requests, non-whole images)."]


def test_every_link_resolves_and_every_reference_is_linked_from_skill_md():
    text = ORCH.read_text(encoding="utf-8")
    links = set(re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", text))
    for link in links:
        assert (ORCH.parent / link).is_file(), f"broken link in SKILL.md: {link}"
    expected = {p.relative_to(ORCH.parent).as_posix() for p in REFS.glob("*") if p.is_file()}
    expected |= {p.relative_to(ORCH.parent).as_posix() for p in (REFS / "phases").glob("*.md")}
    expected.add("references/examples/acme/README.md")
    missing = expected - links
    assert not missing, f"SKILL.md must link every reference directly: {sorted(missing)}"
    for p in list(REFS.rglob("*.md")):
        for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", p.read_text(encoding="utf-8")):
            if not link.startswith("http"):
                assert (p.parent / link).resolve().is_file(), f"broken link in {p.relative_to(ROOT)}: {link}"


def test_long_references_start_with_a_table_of_contents():
    for p in sorted(REFS.rglob("*.md")):
        lines = p.read_text(encoding="utf-8").splitlines()
        if len(lines) > 100:
            assert any(re.match(r"^## Contents", ln) for ln in lines[:15]), f"{p.relative_to(ROOT)} has {len(lines)} lines and no ## Contents near the top"


def test_phase_files_exist_and_stubs_are_short():
    full = {"00-intake", "01-research", "03-strategy-directions", "04-selection", "05-refinement", "06-mark", "07-tokens", "09-qa", "10-book",
            "11-adoption", "12-history", "13-launch"}
    stubs: set = set()
    # the phase's single source is another skill
    pointers = {"02-naming": "../../../brand-naming/SKILL.md", "08-assets": "../../../brand-assets/SKILL.md"}
    have = {p.stem for p in (REFS / "phases").glob("*.md")}
    assert have == full | stubs | set(pointers)
    for s, target in pointers.items():
        text = (REFS / "phases" / f"{s}.md").read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 10, s
        assert f"]({target})" in text and "Inputs" in text and "Outputs" in text and "Gate" in text, s
        assert (REFS / "phases" / target).resolve().is_file(), s
    for s in stubs:
        text = (REFS / "phases" / f"{s}.md").read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 10, s
        assert "stage" in text and "gate" in text.lower() and "Inputs" in text and "Outputs" in text, s
    for f in full:
        text = (REFS / "phases" / f"{f}.md").read_text(encoding="utf-8")
        for h in ("## Goal", "## Inputs", "## Outputs and paths", "## Pitfalls", "## Enforcement"):
            assert h in text, (f, h)
        assert re.search(r"^## (Gate|Gates)\b", text, re.M), f


def test_brand_assets_skill_is_narrow_model_invocable_and_states_the_platform_limits():
    p = SKILLS / "brand-assets" / "SKILL.md"
    fm, body = frontmatter(p)
    assert "disable-model-invocation" not in fm and fm["allowed-tools"] == RULE
    d = fm["description"]
    assert d.startswith("Turns an approved logo or mark into the platform files")
    assert "not for designing or redrawing a logo" in d and "fixing how a page shows a logo" in d
    assert "favicons from my logo.svg" in fm["when_to_use"] and "P8" in fm["when_to_use"]
    for trig in ("favicony z logo", "ikony aplikacji z logo", "plik .ico z logo"):
        assert trig in fm["when_to_use"], trig
    assert "macOS with Xcode" in fm["compatibility"] and "--renderer" in fm["compatibility"]
    assert rules_line(body) == rules_line(ORCH.read_text(encoding="utf-8"))
    flat = " ".join(body.split())
    for needle in ("## Standalone entry", "## Project entry", "./brand-assets/", "INVENTORY.md", "Never trace silently",
                   "potrace", "exit 3, no fallback", "--record-renderer", "Apple builds every size from one master",
                   "favicon layers, `.ico`, PNG icons, tray, Linux hicolor", "downscale --source", "check --project"):
        assert needle in flat, needle
    for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", body):
        assert (p.parent / link).resolve().is_file(), f"broken link in brand-assets: {link}"


def test_qa_phase_lists_every_check_command_and_cites_real_deliberate_break_tests():
    """09-qa: each gate is proven by a test that exists; `(m)` tests really mutate; every check subcommand is in the table."""
    import ast
    text = (REFS / "phases" / "09-qa.md").read_text(encoding="utf-8")
    cited = re.findall(r"`((?:node/)?[\w.]+\.(?:py|mjs))::([^`]+)` \((m|f)\)", text)
    assert len(cited) >= 60, len(cited)

    def body(file, name):
        src = (ROOT / "tests" / file).read_text(encoding="utf-8")
        if file.endswith(".py"):
            for n in ast.parse(src).body:
                if isinstance(n, ast.FunctionDef) and n.name == name:
                    return ast.get_source_segment(src, n)
            return None
        i = src.find(f'test("{name}')
        return None if i < 0 else src[i:src.find("\ntest(", i + 5) % (len(src) + 1)]

    for file, name, kind in cited:
        b = body(file, name)
        assert b, f"09-qa cites a test that does not exist: {file}::{name}"
        mutates = bool(re.search(r"\bmutate(_json|Text)?\(", b))
        assert mutates == (kind == "m"), f"09-qa marks {file}::{name} as ({kind}) but it {'does' if mutates else 'does not'} mutate"
    entry = (ROOT / "bin" / "brand-creator").read_text(encoding="utf-8")
    subs = set(re.findall(r"^  ([a-z][a-z-]+)\)", entry, re.M)) - {"setup", "new", "card", "smoke", "outline-glyphs", "root"}   # root prints the plugin root: not a check
    rows = [ln for ln in text.splitlines() if ln.startswith("| `")]
    for s in subs:
        assert any(re.search(rf"^\| [^|]*`{s}[ `]", ln) for ln in rows), f"check command {s!r} has no row in 09-qa"
    for target in ("web", "social", "apple", "windows", "tray", "tauri", "wallet", "developer"):
        assert any(ln.startswith(f"| `emit {target}`") for ln in rows), target
    for tag in ("`[measured]`", "`[judgement]`", "`[practice]`"):
        assert tag in text, tag
    for kind in ("**gate**", "**warning**", "**judgement**"):
        assert kind in text, kind


def test_wrappers_are_user_invoked_and_call_the_entry_point_in_the_exact_form():
    for w in WRAPPERS:
        p = SKILLS / w / "SKILL.md"
        fm, body = frontmatter(p)
        assert fm["disable-model-invocation"] == "true", w
        assert fm["allowed-tools"] == RULE, w
        if w != "status":
            assert fm["argument-hint"], w
        assert ENTRY in body, w
    status = (SKILLS / "status" / "SKILL.md").read_text(encoding="utf-8")
    assert re.search(r'^!`brand-creator --data "\$\{CLAUDE_PLUGIN_DATA\}" state --project-auto`$', status, re.M)


def test_every_entry_point_call_in_skills_passes_the_data_dir():
    """A call written with --data must pass the plugin data dir; prose may still name subcommands (`brand-creator check`)."""
    n = 0
    for p in sorted(SKILLS.rglob("*.md")):
        for m in re.finditer(r"brand-creator --data(.{0,30})", p.read_text(encoding="utf-8")):
            n += 1
            assert m.group(1).startswith(' "${CLAUDE_PLUGIN_DATA}"'), f"{p.relative_to(ROOT)}: {m.group(0)!r} (always quote the data dir)"
    assert n >= 8


def _status_cmd(data):
    status = (SKILLS / "status" / "SKILL.md").read_text(encoding="utf-8")
    cmd = re.search(r"^!`(.*)`$", status, re.M).group(1)
    return shlex.split(cmd.replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT)).replace("${CLAUDE_PLUGIN_DATA}", str(data)))


def _path_without_uv(tmp_path):
    """bin/ of the plugin (as Claude Code puts it on PATH), python3 and the system folders, but no uv."""
    tools = tmp_path / "pathbin"
    tools.mkdir()
    py = shutil.which("python3")
    assert py, "python3 is needed for this test"
    (tools / "python3").symlink_to(py)
    path = os.pathsep.join([str(tools), str(ROOT / "bin"), "/usr/bin", "/bin"])
    assert shutil.which("uv", path=path) is None, "precondition: uv must be hidden, or this test proves nothing"
    assert shutil.which("brand-creator", path=path) == str(ROOT / "bin" / "brand-creator")
    return path


def test_status_injection_exits_0_with_a_message_outside_a_project(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    env = {**os.environ, "PATH": os.pathsep.join([str(ROOT / "bin"), os.environ["PATH"]])}
    r = subprocess.run(_status_cmd(data), cwd=tmp_path, capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "no brand project found" in r.stdout + r.stderr and "/brand-creator:new" in r.stdout + r.stderr


def test_status_injection_works_on_a_machine_without_uv(tmp_path):
    """S5: a failing injection aborts the whole skill, so `state` must not need uv (it is standard library only)."""
    data = tmp_path / "data"
    data.mkdir()
    env = {**os.environ, "PATH": _path_without_uv(tmp_path)}
    r = subprocess.run(_status_cmd(data), cwd=tmp_path, capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "no brand project found" in r.stdout, (r.returncode, r.stdout, r.stderr)
    proj = tmp_path / "acme"
    proj.mkdir()
    (proj / "BRAND-STATE.md").write_text("---\nslug: acme\nname: Acme\ntier: quick\nphase: P0\n---\n", encoding="utf-8")
    r = subprocess.run(_status_cmd(data), cwd=proj, capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "tier: quick" in r.stdout and "phase: P0" in r.stdout, (r.returncode, r.stdout, r.stderr)


def test_the_readme_permission_rule_matches_every_call_the_skills_make():
    """S2: the optional rule in the README must match the command form the skills really run."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    rules = re.findall(r'"(Bash\([^"]+\))"', readme)
    assert rules == [RULE], rules
    prefix = rules[0][len("Bash("):-1]
    calls = []
    for p in sorted(SKILLS.rglob("*.md")):
        for line in p.read_text(encoding="utf-8").splitlines():
            m = re.search(r'`(brand-creator --data "\$\{CLAUDE_PLUGIN_DATA\}"[^`]*)`', line) or re.match(r'^(brand-creator --data "\$\{CLAUDE_PLUGIN_DATA\}".*)$', line)
            if m:
                calls.append(m.group(1))
    assert len(calls) >= 8, calls
    for c in calls:
        concrete = c.replace("${CLAUDE_PLUGIN_DATA}", "<data-dir>")
        assert fnmatch.fnmatchcase(concrete, prefix), (c, prefix)
    # the old absolute form must be gone, or the rule would silently stop matching it. The one exception is the fallback for a
    # host that does not put bin/ on PATH (a `claude plugin eval` run): named only right after "command not found".
    fallbacks = 0
    for p in sorted(SKILLS.rglob("*.md")):
        text = p.read_text(encoding="utf-8")
        for m in re.finditer(r"bin/brand-creator", text):
            assert text[m.start() - 23:m.end() + 1] == '"${CLAUDE_PLUGIN_ROOT}/bin/brand-creator"', (p, text[m.start() - 60:m.end()])
            assert "command not found" in text[max(0, m.start() - 300):m.start()], (p, "absolute form outside the PATH fallback")
            fallbacks += 1
    assert fallbacks >= 4, fallbacks   # the orchestrator, brand-assets, brand-book and brand-naming


def test_ai_defaults_is_a_generic_reflex_list():
    d = json.loads((REFS / "ai-defaults.json").read_text(encoding="utf-8"))
    ids = [i["id"] for i in d["items"]]
    assert len(ids) == len(set(ids)) >= 15
    kinds = {i["kind"] for i in d["items"]}
    assert {"palette", "type", "device", "layout", "copy"} <= kinds
    for i in d["items"]:
        assert set(i) == {"id", "kind", "pattern", "why_reflex", "argue_with"} and all(i.values()), i
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", json.dumps(d)), "patterns are described in words, never as colour values"


def test_templates_are_self_contained_and_avoid_the_ai_default_cluster():
    for name in ("round-page.html", "board.html", "review/index.html", "card.html"):
        text = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert not re.search(r"""(?:src|href)\s*=\s*["']?(?:https?:)?//""", text), name
        assert "@import" not in text and "url(http" not in text, name
        families = re.findall(r"font(?:-family)?:[^;}]*", text)
        for f in families:
            assert not re.search(r"(?<!sans-)serif|Georgia|Times", f), (name, f)
        if name != "card.html":
            assert 'prefers-color-scheme:dark' in text and ':root[data-theme="dark"]' in text, name
            assert "--sans:ui-sans-serif,system-ui" in text, name


def test_token_templates_carry_both_schemes_and_computed_hex():
    prim = json.loads((ROOT / "templates/tokens/primitives.tokens.json").read_text())
    light = json.loads((ROOT / "templates/tokens/semantic.light.tokens.json").read_text())
    dark = json.loads((ROOT / "templates/tokens/semantic.dark.tokens.json").read_text())
    colours = {k: v for k, v in prim["color"].items() if not k.startswith("$")}
    assert all(v["$value"]["hex"] != "#000000" and v["$value"]["colorSpace"] == "oklch" for v in colours.values())
    lroles = {k for k in light["color"] if not k.startswith("$")}
    droles = {k for k in dark["color"] if not k.startswith("$")}
    assert lroles == droles and {"bg", "text", "muted", "accent"} <= lroles
    assert light["$extensions"]["brand-creator"]["pairs"]
    for group in ("size", "font", "weight", "motion"):
        assert group in prim, group


def test_trigger_evals_cover_english_polish_and_near_misses():
    """dev/trigger-evals.json in skill-creator shape: {skill: [{query, should_trigger}]} for every skill that exists."""
    d = json.loads((ROOT / "dev" / "trigger-evals.json").read_text(encoding="utf-8"))
    assert isinstance(d.pop("$description"), str)
    skills = {p.parent.name: frontmatter(p)[0] for p in all_skills()}
    assert set(d) == set(skills), (set(d) ^ set(skills))
    for name, cases in d.items():
        assert isinstance(cases, list) and cases, name
        for c in cases:
            assert set(c) == {"query", "should_trigger"} and isinstance(c["should_trigger"], bool) and c["query"].strip(), (name, c)
        queries = [c["query"] for c in cases]
        assert len(queries) == len(set(queries)), f"{name}: duplicate query"
        if skills[name].get("disable-model-invocation") == "true":
            assert not any(c["should_trigger"] for c in cases), f"{name} is user-invoked: negatives only"
            continue
        pos = [c["query"] for c in cases if c["should_trigger"]]
        neg = [c["query"] for c in cases if not c["should_trigger"]]
        assert len(pos) >= 10 and len(neg) >= 8, name
        assert sum(1 for q in pos if re.search(r"[ąćęłńóśźż]", q)) >= 3, f"{name}: needs Polish positives"
    bc_pos = " ".join(c["query"] for c in d["brand-creator"] if c["should_trigger"]).lower()
    for word in ("bakery", "coach", "photograph", "podcast", "etsy", "have a logo already"):
        assert word in bc_pos, f"brand-creator positives miss a non-software case: {word}"
    bc_neg = " ".join(c["query"] for c in d["brand-creator"] if not c["should_trigger"]).lower()
    for word in ("blurry on retina", "navbar", "chart", "landing page", "tailwind design system", "slide deck theme", "to rgb",
                 "taken"):
        assert word in bc_neg, f"brand-creator negatives miss the plan's near miss: {word}"
    bn = d["brand-naming"]
    assert any(re.search(r"is the name \w+ (already )?taken", c["query"], re.I) and c["should_trigger"] for c in bn)
    assert any("czy nazwa" in c["query"] and c["should_trigger"] for c in bn)
    bn_neg = " ".join(c["query"] for c in bn if not c["should_trigger"]).lower()
    for word in ("logo", "register the domain", "trademark"):
        assert word in bn_neg, f"brand-naming negatives miss: {word}"
    ba = d["brand-assets"]
    ba_pos = " ".join(c["query"] for c in ba if c["should_trigger"]).lower()
    ba_neg = " ".join(c["query"] for c in ba if not c["should_trigger"]).lower()
    for word in ("favicons from my logo.svg", ".ico", "tray", "app icon", "png"):
        assert word in ba_pos, f"brand-assets positives miss: {word}"
    for word in ("blurry on retina", "navbar", "design a new logo", "resize this png", "guidelines"):
        assert word in ba_neg, f"brand-assets negatives miss the plan's near miss: {word}"
    # platform files from a finished mark: brand-assets yes, brand-creator no; guidelines for an existing logo: the reverse
    assert {c["query"] for c in ba if c["should_trigger"]} & {c["query"] for c in d["brand-creator"] if not c["should_trigger"]}
    assert {c["query"] for c in ba if not c["should_trigger"]} & {c["query"] for c in d["brand-creator"] if c["should_trigger"]}
    # a naming-only request is a sibling case: brand-naming yes, brand-creator no
    shared = {c["query"] for c in bn if c["should_trigger"]} & {c["query"] for c in d["brand-creator"] if not c["should_trigger"]}
    assert shared, "no sibling case shared between brand-naming and brand-creator"


def test_g0_fits_the_ask_user_question_tool_in_every_place_it_is_described():
    """G0 holds at most 3 concrete scope questions (tier, architecture when siblings show, name when open), each with 2 to 4
    options; the mark source is inferred and stated, never asked; free text and the folder do not go in the call. The one
    upload consent (review surface) is the only other item, and only when boards could be uploaded."""
    texts = {p: p.read_text(encoding="utf-8") for p in (ORCH, SKILLS / "new" / "SKILL.md", REFS / "phases" / "00-intake.md")}
    for p, t in texts.items():
        flat = " ".join(t.split())
        assert "at most 3 scope questions" in flat, p
        assert not re.search(r"at most 4 (?:choice )?questions", flat), p
        assert "same AskUserQuestion call" not in flat, p
        assert "plain-text message" in flat or "plain text message" in flat, p
        assert re.search(r"mark source (?:is )?(?:inferred and stated, not asked|is not a question)", flat, re.I), p
        assert "upload question" in flat, p
    intake = " ".join(texts[REFS / "phases" / "00-intake.md"].split())
    assert "2 to 4 choice options" in intake and "(Recommended)" in intake and "Architecture" in intake
    raw = texts[REFS / "phases" / "00-intake.md"]
    g0 = raw[raw.index("## Gate G0"):raw.index("## Pitfalls")]
    numbered = re.findall(r"^(\d)\. \*\*(\w+)", g0, re.M)
    assert [n for n, _ in numbered] == ["1", "2", "3"] and [w for _, w in numbered] == ["Tier", "Architecture", "Name"], numbered
    orch = " ".join(texts[ORCH].split())
    g0_orch = orch[orch.index("**G0 Scope.**"):orch.index("**G1 Name go.**")]
    assert "mark source" in g0_orch and "not asked" in g0_orch and "tier; architecture" in g0_orch
    rubric = (ROOT / "evals" / "g0-asks-scope-before-board" / "graders" / "rubric.md").read_text(encoding="utf-8")
    assert "at most\nthree concrete scope questions" in rubric or "at most three concrete scope questions" in " ".join(rubric.split())


def test_quoting_of_the_data_dir_is_the_same_in_skills_and_in_the_contract():
    """Chosen form: always `--data "${CLAUDE_PLUGIN_DATA}"` (quoted). It must also work when the data path holds a space."""
    contract = (ROOT / "scripts" / "CONTRACT.md").read_text(encoding="utf-8")
    assert 'Skills pass `--data "${CLAUDE_PLUGIN_DATA}"`' in contract
    for p in sorted(SKILLS.rglob("*.md")):
        text = p.read_text(encoding="utf-8")
        assert "--data ${CLAUDE_PLUGIN_DATA}" not in text, f"{p.relative_to(ROOT)} has an unquoted data dir"
    cmd = _status_cmd("/tmp/a dir/data")
    assert cmd[cmd.index("--data") + 1] == "/tmp/a dir/data", cmd  # one argv entry even with a space in the path


def test_status_injection_works_with_a_space_in_the_data_path(tmp_path):
    data = tmp_path / "a data dir"
    data.mkdir()
    env = {**os.environ, "PATH": os.pathsep.join([str(ROOT / "bin"), os.environ["PATH"]])}
    r = subprocess.run(_status_cmd(data), cwd=tmp_path, capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "no brand project found" in r.stdout + r.stderr, (r.returncode, r.stdout, r.stderr)


def _flat(p):
    return " ".join(p.read_text(encoding="utf-8").split())


def test_every_relative_link_in_every_skill_resolves():
    n = 0
    for p in all_skills():
        for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", p.read_text(encoding="utf-8")):
            if not link.startswith(("http", "mailto:")):
                n += 1
                assert (p.parent / link).resolve().is_file(), f"broken link in {p.relative_to(ROOT)}: {link}"
    assert n >= 30, n


def test_brand_book_skill_is_narrow_model_invocable_and_carries_the_method_per_mark_source():
    p = SKILLS / "brand-book" / "SKILL.md"
    fm, body = frontmatter(p)
    assert "disable-model-invocation" not in fm and fm["allowed-tools"] == RULE
    d = fm["description"]
    assert d.startswith("Builds, updates, reviews and exports the brand book")
    assert "not for slide decks, code style guides" in d and "designing a new brand" in d
    for trig in ("księga znaku", "zasady marki", "P10", "brand guidelines", "brand rules page"):
        assert trig in fm["when_to_use"], trig
    assert rules_line(body) == rules_line(ORCH.read_text(encoding="utf-8"))
    flat = " ".join(body.split())
    for needle in ("`generated`, `existing`", "`authored-vector`", "never `book.html`", "`book` refuses", "book --verify", "byte-identical",
                   "--count <N>", "--note", "--new-edition", "Never Edit or Write `book.html` directly", "book-lint --self-consistency",
                   "collapse --group <G> --keep <NAME> --apply", "removed-<date>/", "state --record G5", "approved_edition",
                   "adapters --brand-md --design-md", "applied-skill --yes", "\"not verified\" (exit 3), never a pass", "Without a yes, write neither",
                   "**RGB proof**", "\"RGB, not print-ready\"", "check --cascade"):
        assert needle in flat, needle
    # the self-review checklist: every item of the plan, each with how it is checked
    rows = [ln for ln in body.splitlines() if re.match(r"^\| \d+ \|", ln)]
    assert len(rows) == 10, rows
    for item in ("installed font", "short names", "its own rules", "dated source", "rejected direction", "Every chapter the tier needs",
                 "focus state", "minimum size", "390 px", "Counts and file rows"):
        assert any(item in r for r in rows), item
    assert "[the brand-book skill](../../../brand-book/SKILL.md)" in (REFS / "phases" / "10-book.md").read_text(encoding="utf-8")


def test_brand_adopt_is_user_invoked_and_states_every_safety_rule_of_the_apply():
    p = SKILLS / "brand-adopt" / "SKILL.md"
    fm, body = frontmatter(p)
    assert fm["disable-model-invocation"] == "true" and fm["allowed-tools"] == RULE and fm["argument-hint"]
    assert ENTRY in body and rules_line(body) == rules_line(ORCH.read_text(encoding="utf-8"))
    flat = " ".join(body.split())
    for needle in ("adoption survey", "adoption add", "the owner names it", "never work on the default branch", "state --record G6",
                   "One implementer per repository", "fleet gate", "never two implementers in one working tree", "**by its content**",
                   "reported \"not done\", never guessed", "Never pass `--no-verify`", "Independent review", "`cmp` every file",
                   "the repository's own build and tests", "\"not verified\"", "a fix pass for the findings that need no decision",
                   "\"Decisions for you\"", "three separate asks", "say what the push triggers", "Never call a push safe",
                   "each need their own OK", "byte for byte", "scratch copy of the site", "Propose, do not add unasked", "no placeholder"):
        assert needle in flat, needle
    assert "the brand-adopt skill" in _flat(REFS / "phases" / "11-adoption.md")


def test_check_review_and_launch_wrappers_say_what_they_run():
    check, review, launch = (_flat(SKILLS / s / "SKILL.md") for s in ("check", "review", "launch"))
    assert "check --project <dir> --cascade" in check and "history/MANIFEST.sha256" in check and "Never report a row that did not run as passed" in check
    for needle in ("Self-review (always)", "one approvable list", "Lens panel (optional)", "Default: single-thread", "fleet gate",
                   "explicit yes", "A (before launch), B (soon) and C (optional)", "must not change", "Lenses read; they never edit",
                   "Panels advise"):
        assert needle in review or needle in " ".join((SKILLS / "review" / "SKILL.md").read_text().split()), needle
    for needle in ("launch-todo --project <dir>", "**one action**", "exact click path", "--record G7", "never the act",
                   "available, free or clear", "recheck first"):
        assert needle in launch, needle
    for s in ("review", "launch"):
        assert rules_line((SKILLS / s / "SKILL.md").read_text(encoding="utf-8")) == rules_line(ORCH.read_text(encoding="utf-8")), s


def test_history_launch_and_cascade_references_hold_the_plan_items():
    h = _flat(REFS / "phases" / "12-history.md")
    for needle in ("freeze r<N> --name approved-board", "kept as written", "templates/ADR.md", "Status, Date, Source, Context, Decision, Consequences, Rejected",
                   "**Append, never rewrite.**", "Superseded by ADR-NNNN", "[cascade.md](../cascade.md)", "BRAND-STATE.md is the memory",
                   "rejected, liked or DECIDED", "never holds a second copy"):
        assert needle in h, needle
    adr = (ROOT / "templates" / "ADR.md").read_text(encoding="utf-8")
    assert [ln for ln in adr.splitlines() if ln.startswith("## ")] == ["## Context", "## Decision", "## Consequences", "## Rejected", "## Amendments"]
    for f in ("**Status:**", "**Date:**", "**Source:**", "Superseded by ADR-NNNN", "Append only"):
        assert f in adr, f
    launch = _flat(REFS / "phases" / "13-launch.md")
    steps = re.findall(r"^\d\. \*\*([^*]+)\*\*", (REFS / "phases" / "13-launch.md").read_text(encoding="utf-8"), re.M)
    assert len(steps) == 7 and "Recheck before buying or filing" in steps, steps
    assert launch.count("the date") + launch.count("its date") >= 5
    for needle in ("**name** and a **Lab target**", "Never write that a hex value equals a spot ink", "brand-creator bundles no profile",
                   "**The printer's proof is required**", "PDF/X-4 candidate (preflight with your printer)", "Registers are never queried"):
        assert needle in launch, needle
    c = _flat(REFS / "cascade.md")
    boxes = re.findall(r"^\d\. \[ \] ", (REFS / "cascade.md").read_text(encoding="utf-8"), re.M)
    assert len(boxes) == 9, boxes
    for needle in ("generators", "the parent brand's README and book", "AGENTS.md or CLAUDE.md pointer files", "each `emit` target",
                   "snapshot diff", "verify-idempotent", "check --project <dir> --cascade", "headers and footers", "DMG backgrounds",
                   "NSIS", "Open Graph", "fix every hit in a source, never in an output", "Show the specific section", "ADR"):
        assert needle.lower() in c.lower(), needle


def test_connectors_are_optional_placeholders_and_the_plugin_ships_no_mcp_config():
    assert not (ROOT / ".mcp.json").exists() and "mcpServers" not in (ROOT / ".claude-plugin" / "plugin.json").read_text()
    c = _flat(ROOT / "CONNECTORS.md")
    for needle in ("`~~design tool`", "no `.mcp.json`", "Optional, never assumed", "Writing needs an ask, one action at a time",
                   "External kits are never the source of truth", "tokens/*.tokens.json"):
        assert needle in c, needle
    assert "CONNECTORS.md" in (ROOT / "README.md").read_text() and "(../../CONNECTORS.md)" in ORCH.read_text()


def test_brand_book_trigger_evals_have_the_plan_negatives_and_the_sibling_case():
    d = json.loads((ROOT / "dev" / "trigger-evals.json").read_text(encoding="utf-8"))
    bb = d["brand-book"]
    neg = " ".join(c["query"] for c in bb if not c["should_trigger"]).lower()
    for word in ("make a slide deck", "write a style guide for my code", "favicons", "design a logo"):
        assert word in neg, word
    pos = " ".join(c["query"] for c in bb if c["should_trigger"]).lower()
    for word in ("księgę znaku", "guidelines", "pdf", "hand-drawn", "brand.md"):
        assert word in pos, word
    # a book for a brand that does not exist yet is brand-creator's, not brand-book's
    assert {c["query"] for c in bb if not c["should_trigger"]} & {c["query"] for c in d["brand-creator"] if c["should_trigger"]}


BUILD_LABEL = re.compile(r"(?i)\(stage \d|\bstages? \d+[a-z]?\b|\bstage-\d|later version")


def test_shipped_prose_carries_no_build_stage_labels():
    """Build-stage labels ("(stage 6)", "stage 4a", "in a later version") are history, not behaviour: in shipped prose they tell
    the model and the owner that something is not enforced yet when it is. Name the real command or eval instead."""
    assert BUILD_LABEL.search("behaviour eval (stage 6)") and BUILD_LABEL.search("checked in a later version")
    assert BUILD_LABEL.search("the stage-4 steps") and BUILD_LABEL.search("brand book (stage 4a)")
    assert not BUILD_LABEL.search("| name | stage | reason |") and not BUILD_LABEL.search("the first stage of the workflow")
    hits = []
    for base in (ROOT / "skills", ROOT / "templates"):
        for f in sorted(base.rglob("*")):
            if not f.is_file():
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if BUILD_LABEL.search(line):
                    hits.append(f"{f.relative_to(ROOT)}:{n}: {line.strip()[:100]}")
    usage = (ROOT / "bin" / "brand-creator").read_text(encoding="utf-8")
    hits += [f"bin/brand-creator help: {ln.strip()}" for ln in usage.splitlines() if BUILD_LABEL.search(ln)]
    assert not hits, "build-stage labels in shipped prose:\n" + "\n".join(hits)
