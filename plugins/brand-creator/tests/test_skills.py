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
               "## Scope tiers", "Quick", "Standard", "Full", "## Phase map", "**G0 Scope.**", "**G1 Name go.**", "**G1s Style pick.**",
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
    full = {"00-intake", "01-research", "01s-style-research", "03-strategy-directions", "04-selection", "05-refinement", "06-mark", "07-tokens", "09-qa", "10-book",
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
    assert "favicons from my logo.svg" in fm["when_to_use"] and "icons and images step" in fm["when_to_use"]
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
    """S2: the optional rule in the permissions page must match the command form the skills really run."""
    readme = (ROOT / "docs/manual/reference/permissions.md").read_text(encoding="utf-8")
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
    for name in ("round-page.html", "board.html", "review/index.html", "card.html", "style-board.html"):
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
    for group in ("size", "font", "weight", "motion", "easing"):
        assert group in prim, group
    # curves are tokens now: three proposals until G4, and the motion group no longer says they are only named in the book
    easing = prim["easing"]
    assert easing["$type"] == "cubicBezier" and {k: v["$value"] for k, v in easing.items() if not k.startswith("$")} == {
        "standard": [0.2, 0, 0, 1], "enter": [0, 0, 0, 1], "exit": [0.3, 0, 1, 1]}
    assert "proposals until G4" in easing["$description"]
    assert prim["motion"]["$type"] == "duration" and "cubicBezier" not in prim["motion"]["$description"] and "emitter" not in prim["motion"]["$description"]


def test_the_tokens_phase_says_curves_are_tokens_and_the_motion_template_points_at_the_motion_json():
    phase = " ".join((REFS / "phases" / "07-tokens.md").read_text(encoding="utf-8").split())
    assert "until the emitter supports" not in phase and "Name the curves in the book" not in phase
    g4 = next(ln for ln in (REFS / "phases" / "07-tokens.md").read_text(encoding="utf-8").splitlines() if ln.startswith("- (rule) reduced motion"))
    assert "easing.standard" in g4 and "`enter`" in g4 and "`exit`" in g4 and "`motion.quick`" in g4       # the G4 motion item names the duration and the easing tokens
    assert "facts as data in `motion/motion.json`" in phase and "scripts/CONTRACT.md" in phase and "| Motion spec as data | `motion/motion.json`" in phase
    spec = (ROOT / "templates" / "MOTION-SPEC.md").read_text(encoding="utf-8")
    assert "machine-readable twin" in spec and "`motion/motion.json`" in spec and "`easing.standard`" in spec


def test_trigger_evals_cover_english_polish_and_near_misses():
    """evals/trigger-evals.json in skill-creator shape: {skill: [{query, should_trigger}]} for every skill that exists."""
    d = json.loads((ROOT / "evals" / "trigger-evals.json").read_text(encoding="utf-8"))
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
    for trig in ("księga znaku", "zasady marki", "brand book step", "brand guidelines", "brand rules page"):
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
    d = json.loads((ROOT / "evals" / "trigger-evals.json").read_text(encoding="utf-8"))
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


# ---- the style research gate (P1s, G1s) in the wrappers, the orchestrator, the phase files and the pointers that name them

def test_orchestrator_stays_under_the_line_limit_and_its_top_under_the_character_limit():
    text = ORCH.read_text(encoding="utf-8")
    assert len(text.splitlines()) < 500, f"SKILL.md has {len(text.splitlines())} lines; the standard is under 500 (docs-standard section 5)"
    top = text[: text.index("## Round mechanics")]
    assert len(top) < 20000, f"the top of SKILL.md is {len(top)} characters; only the top survives compaction, the limit is 20000"


def test_the_round_wrapper_builds_round_0_from_the_style_board_and_checks_the_gate_before_any_pick_board():
    p = SKILLS / "round" / "SKILL.md"
    fm, body = frontmatter(p)
    assert fm["argument-hint"] == "[style|pick|refine] [what this round should answer]"
    assert ": " not in fm["description"] and "style board" in fm["description"] and len(fm["description"]) <= 1024
    flat = " ".join(body.split())
    for needle in ("references/phases/01s-style-research.md", "templates/style-board.html", '`data-board="style"`', "round 0", "`rounds/r0/`",
                   "state --project <dir> --require G1s", "Exit 1 means the owner has not picked a style yet", "Never draw a direction first",
                   "pick board of a reset round", "`reset_rounds`", 'state --record G1s "n/a: round 1 drawn before the style step"',
                   "cp rounds/r<N>/board.html review/index.html", "board-lint review/index.html --round <N>",
                   "without web tools say so and stop, and never invent references", "record it with `state --record G1s",
                   "the old pick no longer counts", "`--require G1s` still exits 0 with it", '(no skip: "skipped by owner" is for the first pick board only)',
                   "or `board-lint` fails the board"):
        assert needle in flat, needle
    # the gate is checked before the board is built, and the board before it is linted
    assert flat.index("--require G1s") < flat.index("Build `rounds/r<N>/board.html`") < flat.index("Lint until exit 0")
    assert "[pick|refine]" not in body


def test_the_new_wrapper_says_the_style_research_comes_before_round_1():
    flat = _flat(SKILLS / "new" / "SKILL.md")
    assert "what comes next (category research in Standard and Full, then the style research and its board, then round 1)" in flat
    assert "(research or round 1)" not in flat


def test_the_orchestrator_names_the_style_gate_in_the_gate_reset_review_and_layout_sections():
    text = ORCH.read_text(encoding="utf-8")
    top = " ".join(text[: text.index("## Round mechanics")].split())
    for needle in ("**G1s Style pick.**", "Research needs web access: without web tools say so and stop, never invent references",
                   "Every pick board (round 1, each reset round) waits for G1s", "`state --require G1s`", 'records `G1s "n/a: round 1 drawn before the style step"`',
                   "runs the style research now as round 0 (the hook keeps `rounds/r0/` writable while G1s is empty)",
                   "the style research again (P1s: a new style board in the next round, G1s recorded again)", "Record both rounds in `reset_rounds`",
                   "Round 0's page is a copy of the style board",
                   "(it also writes `g1s_round`, the highest round whose board is a style board)", "Before the first pick board the owner may skip it",
                   "a skip is for the first pick board only, and the old G1s pick does not stand in for the new one"):
        assert needle in top, needle
    below = " ".join(text[text.index("## Round mechanics"):].split())
    assert "`cp rounds/r0/board.html review/index.html`" in below and "board-lint review/index.html --round 0" in below
    assert "after a full rejection the next pick board also waits for a new style board and a new pick (G2b-a)" in below
    layout = text[text.index("## Project layout"):]
    assert "rounds/r0/board.html (style board)" in layout


def test_the_style_research_phase_has_a_no_web_path_thumbnail_rules_and_the_reset_and_in_flight_rules():
    flat = _flat(REFS / "phases" / "01s-style-research.md")
    for needle in ("## No web access", "say that the style research needs web access, and stop", "Never write references, URLs, brand names or descriptions of marks from memory",
                   "allow web access, send links or screenshots", "skip the research",
                   "each reference shows its real mark as a thumbnail where one can be fetched", "from official images (the reference's own site or press page), from Wikimedia Commons images, or from a screenshot",
                   "`research/style-thumbs/`", "downscale a copy to about 240 px wide and inline it", "shown for private research",
                   "never reuse a reference's mark, or a part of it, in a drawing", "the lint fails it",
                   "n/a: round 1 drawn before the style step", "run the style research now as round 0", "A new style board goes in the next round",
                   "also listed in `reset_rounds`", "`/brand-creator:round` skill does it", "the `directions` workflow refuses to start without the G1s record",
                   "copy of the board (`cp rounds/r0/board.html review/index.html`)", "`board-lint review/index.html --round 0`",
                   # the skip is for the first pick board only, and a full rejection re-arms the gate through g1s_round
                   'it cannot be skipped: "skipped by owner" is for the first pick board only', "Before the first pick board the owner may skip it explicitly",
                   "After a full rejection there is no skip", "the tool writes `g1s_round` with it", "fails until a style board in a reset round lies after it",
                   "`g1s_round` is at least that board's round", "r1 pick, r2 style, r3 pick, r4 style, r5 pick", "**The old pick standing in.**",
                   # what the image lint checks, said exactly
                   "every `<img src>` and every `srcset` on a style board is an inlined `data:image/` URI", "in a `<figure>` whose `<figcaption>` says whose mark it is",
                   "a thumbnail also needs alt text and a non-empty caption, and the words of the caption are yours"):
        assert needle in flat, needle
    assert "embed images fetched from it" not in flat, "the old rule against showing the references' images is gone"


def test_the_selection_phase_sends_a_full_rejection_through_the_style_research_again():
    flat = _flat(REFS / "phases" / "04-selection.md")
    for needle in ("run the style research again ([P1s](01s-style-research.md)) before any new territory is drawn", "Show a new style board in the next round",
                   "add that round to `reset_rounds`", "re-record G1s", 'state --record G1s "<the new pick>"', "also added to `reset_rounds`",
                   "`project:style-gate` on the pick board of a reset round (G1s recorded, a new style board in a reset round after the rejected round, `g1s_round` at least that round)",
                   'The style board is required here: "skipped by owner" is for the first pick board only', "the tool also writes `g1s_round`",
                   "so the old pick cannot stand in"):
        assert needle in flat, needle


def test_the_selection_phase_puts_a_screening_override_on_record():
    """An owner who keeps an option the screening or a judge flagged: the override, its reason and the extra check it triggered
    go into BRAND-STATE's Notes, and the check runs before G3 (a real project kept a disqualified box mark this way)."""
    flat = _flat(REFS / "phases" / "04-selection.md")
    for needle in ("**Screening overrides go on record.**", "a likeness to another company's mark, a disqualified option",
                   "`- Screening override <date>: <item>, <why the owner kept it>, <the extra check it triggered>`",
                   "and run that check before G3"):
        assert needle in flat, needle


def test_the_drawing_manual_page_names_option_ids_and_where_board_answers_go():
    flat = _flat(ROOT / "docs" / "manual" / "use" / "get-your-marks-drawn.md")
    for needle in ("Each option has an ID that names its board, such as `family1-bc-3`", "so a choice can't be read two ways",
                   "Give board answers, such as an approval, in your brand-creator session, not the drawing one"):
        assert needle in flat, needle


LAST_FIXES = {   # file (from the plugin folder) -> sentences it says about the last fixes of the style gate
    "scripts/CONTRACT.md": (
        "and so does a pick board: it belongs to round 1 or to a round listed in `reset_rounds` (after a full rejection); later rounds are refine boards",
        "A list key (`reset_rounds`, `book_chapters`) is a flow list", "`state --set reset_rounds=4,5` writes `reset_rounds: [4, 5]` (whole numbers from 1; anything else exits 2)",
        "every reader goes through `State.reset_rounds()`, which takes both and reads runs of digits", '`"[10,11]"` is rounds 10 and 11',
        "an indented line under a key that has a plain value or before the first key (the state reader rejects those too)",
        "the highest round number whose `rounds/rN/board.html` is a style board at that moment (`r0` counts;", "or, when no round holds one, it removes the key",
        "A round folder that only exists, a copy of an earlier board or a style board not written yet does not count",
        "The round and the kind are read from one tag, the `<body>` (or the `<html>` tag when the body carries neither `data-round` nor `data-board`)",
        "`scripts/boardlib/boardpage.py` (outside `scripts/lib/`, so that a change there does not make every pack stale)",
        "it counts only when it declares `data-round=\"M\"` and holds at least four named `territory` sections with content, the minimum of the style lint",
        "r2 has 0 of the 4 territories a style board needs", "`r2 declares data-round=\"0\" (a copied page)`",
        "trims the spaces around the key and the value", "a key that is not one word (letters, digits, `_` and `-`, dots between parts) exits 2",
        "on a page under `rounds/rM/` a different N exits 2",
        "A repeated attribute counts by its first copy, as in a browser"),
    "skills/brand-creator/SKILL.md": ("(it also writes `g1s_round`, the highest round whose board is a style board)",),
    "skills/brand-creator/references/phases/04-selection.md": (
        "also rewrites `g1s_round` (the highest round whose board is a style board)", "(the whole list: `state --set reset_rounds=2,3`;"),
    "skills/brand-creator/references/phases/01s-style-research.md": (
        "the tool also writes `g1s_round`, the highest round whose board is a style board, or drops it when there is none",
        "An r0 style board drawn after round 1 never counts for a reset",
        "show the style board as the next reset round instead (round N, listed in `reset_rounds`), record G1s from it, and draw the pick board in round N+1",
        "r1 rejected, r2 style board, r3 pick board, `reset_rounds` [2, 3]", "(a style board with fewer than 4 territories does not count)"),
    "skills/brand-creator/references/board-contract.md": (
        "that has no newer style board, or no newer pick behind it",
        "a pick board belongs to round 1 or to a reset round, and later rounds are refine boards"),
    "templates/BRAND-STATE.md": ("stores the highest round whose board is a style board at that moment",),
    "docs/adr/ADR-0002-style-research-before-the-first-drawing.md": ("writes `g1s_round`, the highest round whose board is a style board",),
}
LAST_FIXES_GONE = {   # file -> sentences that were true before the fixes and are not any more
    "scripts/CONTRACT.md": ("the highest round number on disk",),
    "skills/brand-creator/SKILL.md": ("the highest round on disk",),
    "skills/brand-creator/references/phases/04-selection.md": ("the highest round on disk",),
    "skills/brand-creator/references/phases/01s-style-research.md": ("the highest round on disk",),
    "skills/brand-creator/references/board-contract.md": ("no newer style board and no newer pick",),
    "templates/BRAND-STATE.md": ("the highest round on disk",),
    "docs/adr/ADR-0002-style-research-before-the-first-drawing.md": ("the highest round on disk",),
}


def test_the_docs_say_what_the_last_fixes_of_the_style_gate_do():
    for rel, needles in LAST_FIXES.items():
        flat = _flat(ROOT / rel)
        for needle in needles:
            assert needle in flat, (rel, needle)
    for rel, needles in LAST_FIXES_GONE.items():
        flat = _flat(ROOT / rel)
        for needle in needles:
            assert needle not in flat, (rel, needle)


def test_the_0_3_0_changelog_tells_the_last_fixes_and_what_an_older_project_sees():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = text.index("## [0.3.0]")
    unreleased = " ".join(text[start:text.index("\n## [", start + 5)].split())
    for needle in (
            # D and E: the style gate counts a real style board, and g1s_round follows it
            "it needs the four named territories with content that the style lint asks for",
            "a copied page that still declares the round it came from does not count either",
            "the highest round whose board is a style board (and removes it when there is none)",
            # the review-4 nits: a padded --set key, and a --round that contradicts the folder
            "Spaces around the key and the value are now trimmed, and a key that is not one word exits 2",
            "A `--round` that contradicts the page's folder now exits 2",
            "a pick recorded before the new style board is written does not count as coming after it",
            "its round and its kind come from one tag, the body (or the html tag when the body has neither)",
            # A: a pick board only in round 1 and in a reset round
            "A pick board belongs to round 1 or to a round listed in `reset_rounds`", "fails a pick board in any later round (`page:data-board`: later rounds are refine boards)",
            # B: the list keys
            '`state --set reset_rounds=[2,3]` saved the text "[2,3]" instead of a list', "so `[10,11]` meant rounds 1, 0, 1 and 1",
            "`state --set` now writes a real list for `reset_rounds` and `book_chapters`", '`"[10,11]"` as rounds 10 and 11',
            # the migration line, with what `check` lints said exactly
            "In an older project, an earlier reset round's pick board fails `board-lint` when it is linted again",
            "`brand-creator check` lints no round itself: it reads the `board-lint` report of the latest round only (`rounds/r<N>/board.html`, N the highest)",
            "so only a round you lint again can fail"):
        assert needle in unreleased, needle
    assert "the highest round on disk" not in unreleased and "when there is no round)" not in unreleased


def test_stale_pointers_name_the_style_step_in_the_contract_the_tier_page_and_the_state_template():
    contract = _flat(ROOT / "scripts" / "CONTRACT.md")
    assert "gates (G0 G1 G1s G2 G2b G3 G4 G5 G6 G7)" in contract and "gates (G0 G1 G2 G2b" not in contract
    assert "rounds/r0/board.html" in contract and "research/style-thumbs/" in contract
    # the state key, the lint rules and what the image rule checks, said exactly
    for needle in ("`state --record G1s` also writes `g1s_round`: the highest round number whose `rounds/rN/board.html` is a style board at that moment",
                   "or, when no round holds one, it removes the key",
                   '`state --set g1s_round=...` (and `--bump`) exits 2 with "written by --record G1s"', "`skipped by owner` (before the first pick board only)",
                   "the highest round below R whose `rounds/r<last>/board.html` is not a style board", "`last < M < R` and M in `reset_rounds`",
                   "after a full rejection, show a new style board in a reset round before the next pick board", "`g1s_round` must be a whole number of at least M",
                   "G1s still holds the pick from before the rejection: record the owner's new pick with state --record G1s",
                   "`skipped by owner` is for the first pick board only", "(r1 pick, r2 style, r3 pick, r4 style, r5 pick)",
                   "every `<img src>`, and every `srcset` on an `<img>` or a `<source>`, is an inlined `data:image/...` URI", "CSS `url()`, `<link>` and SVG `<image>` are not checked",
                   "in a `figure` with a non-empty `figcaption` (a caption naming the owner of the mark", "Words that only start like a label (Stylish, Routes, Looker, Moody) pass",
                   "a repeated `gates:` or a repeated key inside it opens nothing", "`guard.round_is_open`"):
        assert needle in contract, needle
    tier = (ROOT / "docs" / "manual" / "getting-started" / "choose-a-tier.md").read_text(encoding="utf-8")
    quick = next(ln for ln in tier.splitlines() if ln.startswith("| Quick |"))
    assert "style board" in quick and quick.index("style board") < quick.index("one board of 3 directions")
    state = (ROOT / "templates" / "BRAND-STATE.md").read_text(encoding="utf-8")
    assert "every pick board waits for it" in state and "round 1 waits for it" not in state
    assert "the style board run again" in state
    assert "# g1s_round: written by the tool, never by hand." in state and "state --record G1s" in state
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "style board" in readme
    commands = (ROOT / "docs" / "manual" / "reference" / "commands.md").read_text(encoding="utf-8")
    assert "`[style\\|pick\\|refine] [what this round should answer]`" in commands


# ---- the drawing engine step (ADR-0004): the use-llm design canvas, else Claude Code's /design, else Claude-drawn SVG on the owner's yes

ENGINES = REFS / "drawing-engines.md"
TEMPLATES = ROOT / "templates"
MANUAL = ROOT / "docs" / "manual"


def _flat_md(p):
    """The page with blockquote markers removed and whitespace collapsed, so a quoted sentence that wraps still reads as one."""
    return " ".join(re.sub(r"(?m)^\s*>\s?", "", p.read_text(encoding="utf-8")).split())


def test_the_orchestrator_names_the_engine_order_in_one_short_bullet_after_vector_first():
    text = ORCH.read_text(encoding="utf-8")
    top = text[: text.index("## Round mechanics")]
    m = re.search(r"^- \*\*Drawing engine\*\*.*(?:\n  .*)*", top, re.M)
    assert m, "the Two axes list has no Drawing engine bullet"
    assert len(m.group(0)) <= 250, f"the bullet is {len(m.group(0))} characters; the limit is 250"
    flat = " ".join(m.group(0).split())
    assert flat.index("use-llm design canvas") < flat.index("Claude Code's /design") < flat.index("Claude-drawn SVG"), flat
    for needle in ("(the owner types it)", "only on the owner's yes", "Never switch silently", "[drawing-engines.md](references/drawing-engines.md)"):
        assert needle in flat, needle
    assert top.index("## Two axes") < top.index("- **Vector first**") < top.index("- **Drawing engine**") < top.index("- **Architecture**") < top.index("## Phase map")
    assert len(top) < 20000, len(top)


def test_the_drawing_engines_reference_gives_the_order_and_how_to_tell_which_engine_the_session_has():
    raw = ENGINES.read_text(encoding="utf-8")
    flat = _flat_md(ENGINES)
    assert raw.startswith("# Drawing engines\n") and any(re.match(r"^## Contents", ln) for ln in raw.splitlines()[:15])
    # the order: the canvas, else /design, else Claude-drawn SVG
    assert flat.index("**The use-llm design canvas.**") < flat.index("**Claude Code's /design.**") < flat.index("**Claude-drawn SVG.**")
    for needle in ("the canvas, else /design, else Claude-drawn SVG", "The style board (round 0) needs no engine",
                   # how to tell which engine this session has
                   "launched through use-llm (for example `use-claude`)",
                   "`design_guide`, `design_seed`, `dc_write`, `generate_image`, `show_to_user`, `save_screenshot`",
                   "search for `design_guide` with ToolSearch", "Claude Code 2.1.234 and later", "Pro, Max, Team or Enterprise",
                   "publishes an editable artboard as a claude.ai artifact", "Claude cannot start /design",
                   "the owner types `/design` followed by the brief", "tell the owner the exact line to type",
                   "Its docs do not mention image generation: do not claim it generates images", "`claude --version`",
                   # the canvas lands under the folder the session starts in
                   "`<cwd>/.design/<slug>/`", "the drawing session must start in the brand project folder", "untracked",
                   "Check the working folder before the first canvas write",
                   # what the canvas costs and how the owner gives feedback
                   "OpenRouter", "Gemini 3 Pro Image", "$0.135 per image", "9 images $1.21",
                   "The owner looks at the canvas", "screenshots in chat rather than canvas comments",
                   # a placed pixel is drawn too
                   "Placing pixels by hand on a grid is drawing too",
                   "the engine is where the drawing is made and shown, not who places the pixels"):
        assert needle in flat, needle
    assert "Batbelt" not in raw and "jack1913" not in raw, "the reference is general: no project's name in it"


def test_the_drawing_engines_reference_makes_claude_drawn_svg_an_explicit_weaker_choice_on_the_owners_yes():
    flat = _flat_md(ENGINES)
    for needle in ("Claude-drawn SVG is an explicit, weaker choice, and only on the owner's yes",
                   "Only when neither engine above is available, say what is missing and how to get each",
                   "marks drawn this way tend to look generic", "rejected outright",
                   # the kind of sentence to say
                   "I can't draw these marks on a design engine from here", "Do you want me to draw them as SVG?",
                   "(Recommended) so a bare \"ok\" never counts as the yes",
                   # the record, and what happens without a yes
                   "record it as a line in BRAND-STATE.md's Collaboration block", "- Drawing engine: Claude-drawn SVG (owner's yes, <date>)",
                   "Without a yes, draw nothing", "Never switch engines silently"):
        assert needle in flat, needle


def test_the_drawing_engines_reference_says_what_the_brief_must_say_and_what_lands_in_the_round():
    flat = _flat_md(ENGINES)
    for needle in ("`${CLAUDE_PLUGIN_ROOT}/templates/canvas-brief.md`", "`brief/canvas-round-<N>.md`",
                   # the seven things the brief must say
                   "the exact round folder to write to (`rounds/r<N>/<direction>/`)", "which from round 2 starts as a copy of the previous round",
                   "`cp -R rounds/r<N-1> rounds/r<N>` first when the folder is not there yet", "which colour goes to which item",
                   "a target footprint at 16 px", "the dark-background rule for the mark", "a 1 px keyline in the light colour", "a separate dark version",
                   "whether larger grids are redrawn or upscaled: redraw the 32 grid, never upscale",
                   "references that need screening before drawing starts (other companies' marks, platform marks, characters): screening, not clearance",
                   "the image budget: the most images and the most money, in batches of at most 9",
                   # what lands in the round
                   "`rounds/r<N>/<direction>/<item>.svg`", "pure-vector SVG master", "traced with potrace or redrawn, curves fixed by hand",
                   "`shape-rendering=\"crispEdges\"`", "`<item>-16.png`, `<item>-32.png` and `<item>-128.png`", "whole-number scales",
                   "one `SOURCE.md` per direction", "from `templates/SOURCE.md`",
                   "the engine, where the canvas or artboard is, the prompts, the image model, the image count and cost, the trace settings, what was fixed by hand,",
                   "the lineage of each kept mark (option ID, redraws, fixes, file), the agents and tokens of each run, the date",
                   # the eighth slot and the fixed rules the template carries (lessons from a real drawing session)
                   "8. the agent budget, when agents draw: the most agents and tokens per run",
                   "option IDs that name their board (`family1-bc-3`, not \"the 3\")", "gate answers given only in the lead session",
                   "drafts kept in the project (`rounds/r<N>/drafts/`, after G3 `assets/logo/drafts/`), never in a session's scratch folder",
                   "Raw generated images stay on the canvas or in the round as exploration, never as the mark",
                   "the lead session builds the board", "`board-lint`", "`shot`", "reads every slice",
                   # a pick made on the canvas before the board exists
                   "If the owner picks on the canvas before the board exists, record the pick in the owner's own words",
                   "build the board anyway as the record of what was shown"):
        assert needle in flat, needle


def test_the_drawing_engines_reference_carries_the_warnings_and_the_dated_canvas_quirks():
    raw = ENGINES.read_text(encoding="utf-8")
    flat = _flat_md(ENGINES)
    for needle in ("thin bar at 16 px", "crop or redraw for small sizes", "wings or a bat", "tabs along the top read as a crown",
                   "look for readings you did not mean", "156k to 307k agent tokens per run", "The brief sets an agent budget", "say so at the fleet gate",
                   "Render and look before accepting any judge's pixel fix"):
        assert needle in flat, needle
    head = "## Known quirks of the use-llm design canvas (as of 2026-10-20)"
    assert head in raw and raw.index("## Warnings for the drawing step") < raw.index(head)
    quirks = raw[raw.index(head):]
    flat_q = " ".join(quirks.split())
    assert len(re.findall(r"(?m)^- ", quirks)) == 13, "one bullet per field note"
    for needle in ("`E_DESIGN_NO_ADAPTER`", "use the brief's colours", "at most 16 requests per call (prompts x count)", "Send batches of 9",
                   "no running total", "Keep your own tally and an image cap, and say the cost in each reply",
                   "mostly 1024 x 1024", "pad to a square before potrace (turdsize 60 worked)",
                   "Artboard file names cannot contain spaces", "relative `src=`", "do not list them in `design_seed`'s images",
                   "pass the artboards list and the title to `design_seed` explicitly", "the title is required whenever artboards is given",
                   "Write the `.dc.html` from a generator script, then run `design_seed`", "shows such files as stale until they are seeded again",
                   "call `show_to_user` first", "Copy it into `canvas.json` w/h, or the board scrolls", "keep 80 px between artboards",
                   "captures a whole artboard at natural size", "No canvas tool exports a mark (`design_export` ports UI to code)",
                   "(resvg, whole-number scales for pixel marks)", "That does not apply to marks: the mark is the SVG"):
        assert needle in flat_q, needle


def test_the_canvas_brief_template_has_a_slot_for_everything_the_brief_must_say_and_nothing_of_the_real_project():
    text = (TEMPLATES / "canvas-brief.md").read_text(encoding="utf-8")
    flat = " ".join(text.split())
    assert text.startswith("# Round [[fill: N]] drawing brief: ")
    assert len(re.findall(r"\[\[fill: [^\]]+\]\]", text)) >= 25, "too few slots for a brief"
    for needle in (# 1 the exact round folder
                   "Write the round's files only inside `rounds/r[[fill: N]]/`", "`rounds/r[[fill: N]]/[[fill: direction folder]]/`",
                   # ... which from round 2 starts as a copy of the previous round (round 4 of a real project was drawn without it)
                   "the round folder starts as a copy of the previous round", "run `cp -R rounds/r<N-1> rounds/r<N>` first",
                   "the previous round itself is never written to",
                   # 2 which colour goes to which item
                   "which colour goes to which item",
                   # 3 the footprint at 16 px
                   "Footprint at 16 px:", "fill about 14-16 px wide and 12 px or more tall on a 16 grid",
                   # 4 the dark-background rule
                   "On a dark background:", "invert | a 1 px keyline in the light colour | a separate dark version", "a 1 px cream ring fixed it",
                   # 5 larger grids
                   "Larger grids:", "redraw the 32 grid, never upscale the 16 grid",
                   # 6 screening
                   "Screen before drawing:", "other companies' marks, platform marks, characters", "Screening, not clearance",
                   # 7 the image budget
                   "Image budget", "batches of at most 9", "keep your own running tally",
                   # 8 the agent budget, and the fixed rules: option IDs, gate answers, drafts in the project
                   "Agent budget:", "write each run's agents, models and tokens in `SOURCE.md`",
                   "give every option an ID that names its board, the item and the number (for example `family1-bc-3`",
                   'A bare "the 3" means two different options once there are two boards',
                   "Gate answers belong to the lead session", "Never record a gate yourself",
                   "`rounds/r[[fill: N]]/drafts/` while this round is open, `assets/logo/drafts/` once it is approved (G3) and frozen",
                   "never in your session's scratch folder",
                   # where the canvas goes, what lands, and how the marks are made
                   "`<cwd>/.design/<slug>/`", "SOURCE.md", "`shape-rendering=\"crispEdges\"`", "potrace -s -o out.svg -",
                   "Raw generated images stay on the canvas or in the round as exploration, never as the mark"):
        assert needle in flat, needle
    # the rules line is the orchestrator's, verbatim
    assert rules_line(text) == rules_line(ORCH.read_text(encoding="utf-8"))
    # generalised from a real brief: none of that project is left
    assert not re.search(r"#[0-9A-Fa-f]{6}\b", text), "a hex colour from the real brief"
    for word in ("jack1913", "batbelt", "Batbelt", "Woodcut", "Crest", "identicon", "O'Reilly", "/Use" "rs/"):   # split: a home path is itself forbidden here
        assert word not in text, word


def test_the_source_template_holds_the_provenance_fields_of_the_import():
    text = (TEMPLATES / "SOURCE.md").read_text(encoding="utf-8")
    assert text.startswith("# Source of the marks in this folder\n")
    assert "`rounds/r[[fill: N]]/[[fill: direction]]/SOURCE.md`" in text and "One per direction folder" in text
    for field in ("- Direction:", "- Date:", "- Engine:", "- Where the drawing is:", "- Prompts:", "- Image model:", "- Images and cost:",
                  "- Trace settings:", "- Fixed by hand:", "- Lineage:", "- Agents:"):
        line = next((ln for ln in text.splitlines() if ln.startswith(field)), None)
        assert line and "[[fill: " in line, field
    assert "use-llm design canvas | Claude Code /design | Claude-drawn SVG" in text
    assert "| Item | Master | Exports |" in text


def test_the_state_template_and_the_working_style_example_carry_the_drawing_engine_line():
    state = (TEMPLATES / "BRAND-STATE.md").read_text(encoding="utf-8")
    block = state[state.index("## Collaboration"):state.index("## Directions")]
    line = next((ln for ln in block.splitlines() if ln.startswith("- Drawing engine:")), None)
    assert line and "not chosen yet" in line, block
    for value in ("use-llm design canvas", "Claude Code /design", "Claude-drawn SVG"):
        assert value in line, value
    assert "{{" not in line
    assert "- Drawing engine: not chosen yet" in _flat(REFS / "working-style.md")


def test_the_phase_files_the_round_wrapper_and_the_indexes_point_at_the_drawing_engines():
    for phase in ("03-strategy-directions", "05-refinement", "06-mark"):
        text = (REFS / "phases" / f"{phase}.md").read_text(encoding="utf-8")
        assert text.count("](../drawing-engines.md)") >= 1, phase
    assert "The marks are drawn on a drawing engine before the board is built" in _flat(REFS / "phases" / "03-strategy-directions.md")
    flat = _flat(SKILLS / "round" / "SKILL.md")
    link = "${CLAUDE_PLUGIN_ROOT}/skills/brand-creator/references/drawing-engines.md"
    assert flat.count(link) == 1 and flat.index("Build `rounds/r<N>/board.html`") < flat.index(link) < flat.index("Lint until exit 0")
    assert "on a drawing engine, never silently by you" in flat
    # the orchestrator's own round steps and the project layout name the drawing step and its files
    orch = _flat(ORCH)
    assert "Marks that need drawing are drawn first, on the session's drawing engine" in orch[orch.index("## Round mechanics"):]
    layout = ORCH.read_text(encoding="utf-8")
    layout = layout[layout.index("## Project layout"):]
    for needle in ("brief/canvas-round-<N>.md", "<item>.svg, -16/-32/-128.png, SOURCE.md", ".design/<slug>/"):
        assert needle in layout, needle
    contract = _flat(ROOT / "scripts" / "CONTRACT.md")
    for needle in ("rounds/r<N>/<direction>/<item>.svg", "brief/canvas-round-<N>.md", ".design/<slug>/"):
        assert needle in contract, needle
    index = (REFS / "_index.md").read_text(encoding="utf-8")
    assert any(ln.startswith("| [drawing-engines.md](drawing-engines.md) | ") for ln in index.splitlines())
    skill = ORCH.read_text(encoding="utf-8")
    assert "- [drawing-engines.md](references/drawing-engines.md): " in skill[skill.index("## References"):]


def test_adr_0004_records_the_engine_order_and_is_listed():
    adrs = sorted((ROOT / "docs" / "adr").glob("ADR-0004-*.md"))
    assert len(adrs) == 1, adrs
    text = adrs[0].read_text(encoding="utf-8")
    flat = " ".join(text.split())
    assert re.fullmatch(r"ADR-0004-[a-z0-9-]+\.md", adrs[0].name) and text.startswith("# ADR-0004: ")
    assert "- **Status:** accepted" in text and "- **Date:** 2026-10-20" in text
    assert re.findall(r"^## (.+)$", text, re.M) == ["Context", "Decision", "Consequences"]
    for needle in ("ADR-0002", "ADR-0003", "rejected", "code geometry", "Claude Code's /design", "2.1.234", "Claude cannot start it",
                   "an explicit, weaker choice", "the owner's explicit yes", "Collaboration block of BRAND-STATE.md",
                   "Never switch engines silently", "Placing pixels by hand on a grid is drawing too", "`SOURCE.md`", "The style board needs no engine"):
        assert needle in flat, needle
    decision = flat[flat.index("## Decision"):flat.index("## Consequences")]
    assert decision.index("use-llm design canvas") < decision.index("Claude Code's /design") < decision.index("Claude-drawn SVG"), decision
    readme = (ROOT / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
    row = next((ln for ln in readme.splitlines() if ln.startswith("| [ADR-0004]")), None)
    assert row and f"]({adrs[0].name})" in row and row.rstrip().endswith("| accepted |"), row


def test_the_directions_workflow_is_offered_only_after_the_yes_to_claude_drawn_svg():
    """Review of the drawing-engine step, B1: the workflow's designers draw the marks themselves, which is the weaker way."""
    for path, needle in ((REFS / "phases" / "03-strategy-directions.md", "Offer the workflow only after the owner's yes to that way"),
                         (REFS / "fleet.md", "offer it only after the owner's yes to that weaker way"),
                         (MANUAL / "reference" / "agents-and-workflows.md", "Claude offers it only after your yes to that weaker way")):
        assert needle in _flat(path), (path.name, needle)


def test_the_mark_source_says_kept_as_code_and_images_wait_for_the_budget():
    """generated is how a master is kept, not how it is drawn; and no paid image is made before the owner agrees to the budget."""
    top = ORCH.read_text(encoding="utf-8")
    top = " ".join(top[: top.index("## Round mechanics")].split())
    assert "`generated` (kept as code:" in top and "Compass is kept as code, so generated" in top
    for path in (ORCH, REFS / "phases" / "00-intake.md", REFS / "phases" / "06-mark.md", MANUAL / "use" / "start-a-brand.md",
                 MANUAL / "getting-started" / "make-your-first-brand.md"):
        assert "drawn by code" not in _flat(path), path.name
    assert "generate no image until the owner agrees to the image budget" in _flat_md(ENGINES)
    assert "Generate none until the owner has agreed to this budget" in (TEMPLATES / "canvas-brief.md").read_text(encoding="utf-8")
    assert "generates no pictures until you agree to the limit in the brief" in _flat_md(MANUAL / "use" / "get-your-marks-drawn.md")
    acme = (REFS / "examples" / "acme" / "BRAND-STATE.md").read_text(encoding="utf-8")
    assert "- Drawing engine: not chosen yet" in acme[acme.index("## Collaboration"):acme.index("## Directions")]


def test_the_0_3_0_changelog_has_one_added_bullet_for_the_drawing_engines():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = text.index("## [0.3.0]")
    unreleased = text[start:text.index("\n## [", start + 5)]
    added = unreleased[unreleased.index("### Added"):unreleased.index("### Changed")]
    mine = [b for b in re.findall(r"(?m)^- .*(?:\n  .*)*", added) if "design canvas" in b]
    assert len(mine) == 1, mine
    flat = " ".join(mine[0].split())
    assert flat.index("use-llm design canvas") < flat.index("`/design`") < flat.index("draws the marks as SVG itself"), flat
    for needle in ("use-llm design canvas", "`/design`", "which you type because Claude can't start it", "only after your yes",
                   "`brief/canvas-round-<N>.md`", "`SOURCE.md`", "Claude says the cost in each reply"):
        assert needle in flat, needle


def test_the_manual_explains_the_drawing_step_on_one_task_page_and_in_costs_and_limits():
    page = MANUAL / "use" / "get-your-marks-drawn.md"
    text = page.read_text(encoding="utf-8")
    flat = _flat_md(page)
    assert text.startswith("# Get your marks drawn\n")
    for heading in ("## Before you start", "## Get the marks drawn", "## If neither tool is there", "## What it costs", "## Check it worked",
                    "## If something goes wrong", "## Related"):
        assert heading in text, heading
    before = flat[flat.index("Before you start"):flat.index("Get the marks drawn")]
    assert before.index("a design canvas") < before.index("Claude Code's own `/design`"), before
    for needle in ("`use-claude`", "([which one](../reference/claude-code-versions.md))", "Pro, Max, Team or Enterprise", "Claude can't start `/design` for you",
                   "tells you the exact line to type", "/design Read brief/canvas-round-1.md and draw what it asks.",
                   "only if you say yes", "A plain \"ok\" never counts as that yes", "tend to look generic",
                   "each picture costs money", "OpenRouter", "`BRAND-STATE.md`", "`SOURCE.md`", "`.design/`"):
        assert needle in flat, needle
    # a user page: no gate or phase numbers, no decision numbers
    assert not re.search(r"\b(?:G\d[a-z]?|P\d{1,2}s?|ADR-\d+)\b", text), re.findall(r"\b(?:G\d[a-z]?|P\d{1,2}s?|ADR-\d+)\b", text)
    index = (MANUAL / "README.md").read_text(encoding="utf-8")
    assert "- [Get your marks drawn](use/get-your-marks-drawn.md): " in index
    assert "(get-your-marks-drawn.md)" in (MANUAL / "use" / "pick-and-refine-a-direction.md").read_text(encoding="utf-8")
    costs = (MANUAL / "reference" / "costs.md").read_text(encoding="utf-8")
    assert "**Generated pictures only after you agree.**" in costs and "OpenRouter" in costs and "(../use/get-your-marks-drawn.md)" in costs
    limits = " ".join((MANUAL / "reference" / "what-it-never-does.md").read_text(encoding="utf-8").split())
    assert "**No marks drawn in code without your yes.**" in limits and "never starts `/design` for you" in limits
    versions = (MANUAL / "reference" / "claude-code-versions.md").read_text(encoding="utf-8")
    assert "| `/design`, the second way to get marks drawn | 2.1.234 |" in versions
