"""Content tests for the onboard-repo skill, ported from claude-configs.

Three tests that read claude-configs' own docs/adr/ files were left behind; the
stamped-in-this-repo checks of test_dogfood.py do not apply here either.
"""
import ast
import importlib
import json
import os
import pathlib
import re
import sys

import pytest

ONBOARD = pathlib.Path(__file__).resolve().parent.parent / "plugins" / "batbelt" / "skills" / "onboard-repo"
SCRIPTS = ONBOARD / "scripts"
sys.path.insert(0, str(SCRIPTS))
import onboard_lib as lib  # noqa: E402

BEGIN = "<!-- BEGIN REPO SPECIFICS (preserved on --sync) -->"
END = "<!-- END REPO SPECIFICS -->"


def _stamped(inner):
    return "# skill\n\ntemplate body\n\n" + BEGIN + inner + END + "\n"


def _seed(tmp_path, rel, body):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


# ---- Task 1: two-region parsing + preservation ---------------------------


def test_parse_regions_splits_one_well_formed_block():
    before, inner, after = lib.parse_regions(_stamped("\nrepo facts\n"))
    assert "template body" in before
    assert inner == "\nrepo facts\n"
    assert after == "\n"


@pytest.mark.parametrize(
    "text",
    [
        "no markers at all",
        "# only begin\n" + BEGIN + "\nx\n",  # missing END
        "# only end\nx\n" + END + "\n",  # missing BEGIN
        END + "\nx\n" + BEGIN + "\n",  # reversed
        _stamped("\na\n") + BEGIN + "\nb\n" + END,  # duplicate block
    ],
)
def test_parse_regions_fails_closed(text):
    with pytest.raises(lib.MarkerError):
        lib.parse_regions(text)


def test_preserve_keeps_old_specifics_and_updates_template():
    old = "# OLD template\n\n" + BEGIN + "\nVERSION HOME: package.json\n" + END + "\n"
    new = "# NEW template body\n\n" + BEGIN + "\nPLACEHOLDER\n" + END + "\n"
    merged = lib.preserve_repo_specifics(old, new)
    assert "NEW template body" in merged  # template region updated
    assert "VERSION HOME: package.json" in merged  # repo specifics preserved
    assert "PLACEHOLDER" not in merged  # template's placeholder replaced
    assert "OLD template" not in merged


def test_preserve_fails_closed_on_malformed_old():
    with pytest.raises(lib.MarkerError):
        lib.preserve_repo_specifics("no markers", _stamped("\nx\n"))


def test_preserve_fails_closed_on_malformed_new_template():
    with pytest.raises(lib.MarkerError):
        lib.preserve_repo_specifics(_stamped("\nx\n"), "template lost its markers")


# ---- Task 2: predecessor detection (content heuristic) -------------------


def test_classify_by_content_not_name():
    assert (
        lib.classify_artifact("Update CHANGELOG.md per Keep a Changelog and SemVer") == "changelog"
    )
    assert lib.classify_artifact("Audit README and docs/ for documentation drift") == "docs"
    assert lib.classify_artifact("Generate API reference from OpenAPI") is None  # unrelated


def test_find_predecessors_detects_divergent_and_ignores_noise(tmp_path):
    claude = tmp_path / ".claude"
    _seed(
        claude,
        "skills/docs-sync/SKILL.md",
        "Keep README and docs/ in sync with the code; fix doc drift.",
    )
    _seed(
        claude,
        "commands/update-changelog.md",
        "Bump the version and update CHANGELOG.md (Keep a Changelog).",
    )
    _seed(claude, "skills/docs/SKILL.md", "Generate protobuf stubs.")  # bare name, unrelated body
    _seed(
        claude,
        "skills/changelog-release/SKILL.md",
        "our canonical changelog skill",  # canonical -> skip
    )

    found = lib.find_predecessors(claude)
    names = {f["name"]: f["kind"] for f in found}
    assert names == {"docs-sync": "docs", "update-changelog": "changelog"}
    assert all("excerpt" in f and f["path"] for f in found)


def test_find_predecessors_empty_when_no_claude_dir(tmp_path):
    assert lib.find_predecessors(tmp_path / ".claude") == []


# ---- Task 3: CLI seam ----------------------------------------------------


def _load_cli():
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("onboard")


def _load_check():
    # The standing gates live in their own module (ADR-0008) -- it is what gets
    # stamped into a maintained repo, so tests reach for it directly rather than
    # through onboard.py, which merely delegates.
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("check")


_DELEGATED = [
    ["check-docs", "docs"],
    ["check-docs", "docs", "--only", "docs/manual/a.md"],
    ["check-instructions", "rules"],
    ["check-instructions", "rules", "more"],
    ["redact", "raw.txt", "--home", "/h", "--user", "bob", "--stamp", "S"],
    ["redact", "raw.txt", "--home", "/h", "--user", "bob", "--stamp", "S", "--extra", "sekret"],
]


def _verbs_check_serves():
    """The verbs check.py itself answers -- the authoritative list.

    Read from `check.main`'s `cmd == "..."` branches, NOT from onboard.py's dispatcher.
    Deriving the list from the delegating side was shape-sensitive and evadable six
    ways (`elif`, `cmd in (...)`, dict dispatch, `match/case`, `"x" == cmd`, an aliased
    `import check as chk`) -- and worse, an `elif` made the walk credit the PRECEDING
    branch, so it failed naming the wrong verb, which is the direction that gets a test
    loosened rather than a bug fixed. check.py's own dispatcher is the thing that
    defines what must be delegated, so it is what gets parsed.
    """
    # Scanned over the WHOLE module, not a named function: the dispatch moved from
    # `main` into `run` when the two entry points were made to share a handler, and a
    # walk anchored to `main` silently found zero verbs -- which the non-emptiness
    # assert caught, but only because it was there.
    tree = ast.parse((SCRIPTS / "check.py").read_text(encoding="utf-8"))
    verbs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name):
            if node.left.id == "cmd":
                for c in node.comparators:
                    if isinstance(c, ast.Constant) and isinstance(c.value, str):
                        verbs.add(c.value)
                    elif isinstance(c, (ast.Tuple, ast.List, ast.Set)):
                        verbs.update(
                            e.value
                            for e in c.elts
                            if isinstance(e, ast.Constant) and isinstance(e.value, str)
                        )
    return verbs


def test_every_verb_check_serves_is_delegated_and_covered():
    """Three things must agree: what check.py serves, what onboard.py forwards, what
    the parity suite exercises. Any gap re-creates the ADR-0008 shape one level in."""
    served = _verbs_check_serves()
    assert served, "no verbs found in check.main -- the AST walk broke"
    covered = {argv[0] for argv in _DELEGATED}
    assert served <= covered, (
        "check.py serves these verbs but no parity case exercises them: "
        + ", ".join(sorted(served - covered))
    )
    # ...and onboard.py must actually forward each one. Shape-independent: just run it
    # and require the delegation to be reached, rather than pattern-matching the source.
    onb = (SCRIPTS / "onboard.py").read_text(encoding="utf-8")
    missing = [v for v in sorted(served) if '"%s"' % v not in onb]
    assert not missing, "onboard.py has no branch for: " + ", ".join(missing)


def _delegation_fixture(tmp_path):
    # Rich enough that every argument under test CHANGES the output -- two pages so
    # --only restricts to one, and a second roots dir so a dropped trailing arg shows.
    #
    # Deliberately NOT `--repo-root`: the citation resolver accepts any file whose path
    # ENDS with the cited one, so `src/real.py` resolves from the cwd with or without
    # `--repo-root src`. That flag is real but output-invariant here, which would make
    # it useless as a parity probe -- the same vacuity this fixture exists to avoid.
    _seed(tmp_path, "docs/manual/a.md", "# A\n\nSee [gone](./missing.md).\n")
    _seed(tmp_path, "docs/manual/b.md", "# B\n\nSee [alsogone](./nope.md).\n")
    _seed(tmp_path, "rules/r.md", "---\npaths: nope/**\n---\n\nSee `no/such.py:9`.\n")
    _seed(tmp_path, "more/s.md", "---\npaths: alsonope/**\n---\n\nSee `other/gone.py:4`.\n")
    # `sekret` is what makes the two redact variants differ: only the --extra form
    # strips it, so a delegation that drops trailing args shows up as identical output.
    _seed(tmp_path, "raw.txt", "bob ran it from /h and pasted sekret at S\n")


def _run(mod, argv, capsys, tmp_path):
    """(rc, stdout, stderr). stderr is captured because parity that ignores it is not
    parity: onboard.py wraps each delegation in its OWN try/except, so an exception
    escaping a cmd_* function would be reported with a different message by each entry
    point while stdout stayed byte-identical."""
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        rc = mod.main(list(argv))
    finally:
        os.chdir(cwd)
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


@pytest.mark.parametrize("argv", _DELEGATED)
def test_onboard_py_delegates_the_moved_verbs_without_changing_output(tmp_path, capsys, argv):
    """`onboard.py <verb>` must stay a pure pass-through to `check.py <verb>`.

    ADR-0008 moved three verbs and left onboard.py delegating so existing call sites
    keep working. That parity was verified by hand against the pre-split build -- a
    claim nobody can re-run once the old build is gone -- so what gets PINNED here is
    the durable half: the two entry points must agree, forever. A future edit to
    cmd_check_docs that only onboard.py's wrapper compensates for breaks this.
    """
    cli, chk = _load_cli(), _load_check()
    _delegation_fixture(tmp_path)
    rc_d, out_d, err_d = _run(chk, argv, capsys, tmp_path)
    rc_v, out_v, err_v = _run(cli, argv, capsys, tmp_path)
    assert rc_d == rc_v
    assert out_d == out_v
    # stderr may differ ONLY in the program name a usage line reports.
    assert err_d.replace("check.py", "<prog>") == err_v.replace("onboard.py", "<prog>")
    assert out_d.strip(), f"{argv} produced no findings -- fixture is inert"


@pytest.mark.parametrize("argv", [a for a in _DELEGATED if len(a) > 2])
def test_dropping_any_single_argument_changes_the_output(tmp_path, capsys, argv):
    """Per-ARGUMENT vacuity guard. Set-distinctness was not enough.

    The previous guard only required each argv variant to differ from its neighbours by
    *something*, which never ties a specific flag to the difference: a fixture was
    constructed where `--user` and `--stamp` could both be dropped from the delegation
    and all six outputs stayed distinct (because `--extra` alone separated the redact
    pair), so every parity case passed while two flags went unread.

    So drop each argument in turn and require the result to change. If it does not,
    that argument is inert here and proves nothing about pass-through.
    """
    chk = _load_check()
    _delegation_fixture(tmp_path)
    base = _run(chk, argv, capsys, tmp_path)[1:]
    for i in range(1, len(argv)):
        trimmed = argv[:i] + argv[i + 1 :]
        try:
            got = _run(chk, trimmed, capsys, tmp_path)[1:]
        except Exception:  # a malformed trim is a change too
            continue
        assert got != base, (
            f"dropping {argv[i]!r} from {argv} changed nothing -- that argument is "
            f"inert, so the parity case cannot detect it being swallowed"
        )


@pytest.mark.parametrize(
    "argv",
    [
        ["redact", "cap.txt"],  # all three required flags absent
        ["redact", "cap.txt", "--user", "u", "--stamp", "s", "--home"],  # value swallowed
        ["check-docs", "docs", "--forbidden"],
        ["check-docs", "docs", "--captures"],
        ["check-docs", "docs", "--only"],
        ["check-docs", "docs", "--only", "docs/manual/TYPO.md"],
        ["check-docs", ""],
        ["check-instructions", "rules", "--repo-root"],
    ],
)
def test_an_argument_that_would_silently_do_nothing_is_a_usage_error(tmp_path, capsys, argv):
    """Every one of these used to exit 0 having done nothing of what was asked.

    A value-taking flag in last position took a silent default (`next(it, "")`), so
    `--forbidden` at the end scanned for no tokens and passed a tree containing the one
    it was given; `--repo-root` at the end resolved against the cwd; `redact` with no
    `--home/--user/--stamp` echoed the capture back unredacted and exited 0, which is a
    privacy gate reporting success having stripped nothing. `--only` with a typo scoped
    reporting to the empty set while the unscoped scan of the same tree exited 1.

    They share one shape -- **an argument that quietly does nothing** -- and one fix:
    exit 2. This is the same defect class as the unresolved `<index>` placeholder that
    made the stamped `check-docs` recipe pass without opening the index doc.
    """
    chk = _load_check()
    _delegation_fixture(tmp_path)
    _seed(tmp_path, "cap.txt", "/Users/someone/x $ tool\n")
    rc = _run(chk, argv, capsys, tmp_path)[0]
    assert rc == 2, f"{argv} should be a usage error, got rc={rc}"


def test_both_entry_points_report_a_decode_error_identically(tmp_path, capsys):
    # onboard.py delegates through check.run, so the handler is shared. It was not:
    # the same undecodable capture printed "malformed input" one way and "malformed
    # manifest" the other. A decode error is the case a parse-error sweep misses.
    cli, chk = _load_cli(), _load_check()
    (tmp_path / "raw.bin").write_bytes(b"\xff\xfe\x00bad")
    argv = ["redact", "raw.bin", "--home", "/h", "--user", "bob", "--stamp", "S"]
    assert _run(chk, argv, capsys, tmp_path) == _run(cli, argv, capsys, tmp_path)


def test_a_usage_error_names_the_file_the_operator_actually_ran(tmp_path, capsys):
    # The one place the two entry points MAY differ: a usage line naming check.py when
    # the operator typed onboard.py would send them to a file they never invoked.
    cli, chk = _load_cli(), _load_check()
    for verb in ("check-docs", "check-instructions", "redact"):
        assert chk.main([verb]) == 2
        assert ("usage: check.py " + verb) in capsys.readouterr().err
        assert cli.main([verb]) == 2
        assert ("usage: onboard.py " + verb) in capsys.readouterr().err


def test_an_operator_supplied_path_is_never_rewritten_by_the_prog_swap(capsys, tmp_path, monkeypatch):
    """The prog rename must touch the usage line only, never the message body.

    `_usage` began as a blanket `msg.replace("check.py", prog)`, but most messages
    through it are `ERROR: not found: <path>` echoing a path the operator typed --
    so a path that merely CONTAINED the program name was silently edited, reporting a
    file absent from the command and sending the reader somewhere it never was.
    """
    # The `docs` root must exist in the cwd so the --captures case gets past root checks;
    # in claude-configs the repo root happened to provide it.
    (tmp_path / "docs").mkdir()
    monkeypatch.chdir(tmp_path)
    cli = _load_cli()
    for argv, needle in [
        (["check-instructions", "/nope/scripts/check.py"], "/nope/scripts/check.py"),
        (["check-instructions", ".", "--repo-root", "/gone/check.py/x"], "/gone/check.py/x"),
        # roots are validated first, so this exercises check-docs' own root error
        (["check-docs", "/absent/check.py"], "/absent/check.py"),
        # ...and this one gets past roots to the --captures error
        (["check-docs", "docs", "--captures", "/no/check.py"], "/no/check.py"),
        # the two --coverage sites, named explicitly: they were reachable only through
        # a neighbouring case, so a regression at either was pinned by luck
        (["check-docs", "docs", "--coverage", "/gone/check.py/c.json"], "/gone/check.py/c.json"),
        (["check-docs", "docs", "--coverage", "check.py"], "check.py"),
    ]:
        assert cli.main(argv) == 2
        err = capsys.readouterr().err
        assert needle in err, f"{argv} mangled the operator's path: {err.strip()!r}"
        assert "onboard.py" not in err.split("usage:")[0], (
            f"{argv} leaked the delegating program name into an error body: {err.strip()!r}"
        )


def test_cli_preserve_and_check_markers(tmp_path):
    cli = _load_cli()
    old = tmp_path / "old.md"
    old.write_text("# OLD\n\n" + BEGIN + "\nHOME: pkg.json\n" + END + "\n", encoding="utf-8")
    assert cli.main(["check-markers", str(old)]) == 0
    bad = tmp_path / "bad.md"
    bad.write_text("no markers", encoding="utf-8")
    assert cli.main(["check-markers", str(bad)]) == 2


def test_cli_find_predecessors_json(tmp_path, capsys):
    cli = _load_cli()
    claude = tmp_path / ".claude"
    _seed(claude, "skills/docs-sync/SKILL.md", "Keep README and docs/ in sync; fix doc drift.")
    assert cli.main(["find-predecessors", str(claude)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["name"] == "docs-sync" and out[0]["kind"] == "docs"


def test_cli_renumber_toc(tmp_path):
    cli = _load_cli()
    f = _seed(tmp_path, "toc.md", "3. [a](a.md)\n1. [b](b.md)\n")
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(["renumber-toc", str(f)])
    assert rc == 0
    assert "1. [a](a.md)" in buf.getvalue() and "2. [b](b.md)" in buf.getvalue()


def test_cli_write_manifest_then_rewrite_links(tmp_path):
    cli = _load_cli()
    import contextlib
    import io

    pairs = _seed(tmp_path, "pairs.json", '[["a.md", "docs/manual/a.md"]]')
    dirs = _seed(tmp_path, "dirs.json", '["docs/manual"]')
    man = tmp_path / "moves.json"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(["write-move-manifest", str(pairs), str(dirs)])
    assert rc == 0
    man.write_text(buf.getvalue(), encoding="utf-8")
    # the manifest round-trips through read + rewrite-links
    page = _seed(tmp_path, "p.md", "[x](a.md) and open('a.md')\n")
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        rc2 = cli.main(["rewrite-links", str(page), str(man)])
    assert rc2 == 0
    out = buf2.getvalue()
    assert "[x](docs/manual/a.md)" in out and "open('a.md')" in out


def test_cli_rewrite_links_malformed_manifest_exits_2(tmp_path, capsys):
    cli = _load_cli()
    page = _seed(tmp_path, "p.md", "[x](a.md)\n")
    bad = _seed(tmp_path, "bad.json", "not json at all")
    rc = cli.main(["rewrite-links", str(page), str(bad)])
    assert rc == 2
    assert "Traceback" not in capsys.readouterr().err


# ---- Task 4: skill file + references + template blocks --------------------


def test_skill_orchestrates_helpers_and_prints_restart_notice():
    body = (ONBOARD / "SKILL.md").read_text(encoding="utf-8")
    assert "scripts/onboard.py" in body  # invokes the CLI seam
    assert "Restart Claude Code" in body  # restart notice (spec 4.2)
    assert "--sync" in body and "--check" in body  # modes documented
    assert "python3" in body.lower()  # can run the helper
    fm = body.split("---", 2)[1]  # frontmatter
    assert "python3" in fm  # Bash(python3:*) present


def test_skill_always_asks_about_update_deps():
    # update-deps mutates manifests/lockfiles, so it is never stamped silently
    # and never skipped silently: every default run asks once, defaulting to no.
    body = (ONBOARD / "SKILL.md").read_text(encoding="utf-8")
    assert "always asked" in body.lower()
    assert "--without update-deps" in body  # explicit decline is available
    assert "--with update-deps" in body  # explicit accept is available
    low = body.lower()
    assert "default is no" in low  # empty answer declines
    # a repo with no supported ecosystem is reported, never stamped as a no-op
    assert "no supported ecosystem" in low
    assert "never stamp" in low or "never silently stamp" in low


def test_stamping_reference_defines_provenance_and_regions():
    ref = (ONBOARD / "references" / "stamping.md").read_text(encoding="utf-8")
    assert "stamped by onboard-repo v" in ref
    assert "BEGIN REPO SPECIFICS (preserved on --sync)" in ref
    assert "END REPO SPECIFICS" in ref


def _stampable_templates():
    """Every carried skill template, DISCOVERED from disk rather than listed.

    A hardcoded list silently exempts a newly added template from every invariant
    below -- which is exactly what happened when `update-rules` was added: the whole
    suite stayed green while the new template was checked by nothing.
    """
    found = sorted(p.parent.name for p in (ONBOARD / "templates").glob("*/SKILL.md") if p.is_file())
    assert found, "no skill templates discovered under templates/*/SKILL.md"
    return found


def test_templates_have_a_repo_specifics_block_and_are_not_intent_only():
    names = _stampable_templates()
    # update-deps is the one stamped skill that mutates dependencies, so it alone is
    # slash-only; every other template must stay model-invocable.
    for name in names:
        t = (ONBOARD / "templates" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "BEGIN REPO SPECIFICS (preserved on --sync)" in t, name
        assert "END REPO SPECIFICS" in t, name
        if name != "update-deps":
            assert "disable-model-invocation" not in t, name
        lib.parse_regions(t)  # shipped template parses as a single well-formed block


def test_every_carried_template_is_wired_into_the_stamping_flow():
    # A template nobody stamps is dead weight, and the failure is silent: the file
    # ships, the suite passes, and no repo ever receives it.
    skill = SKILL.read_text(encoding="utf-8")
    stamping = (ONBOARD / "references" / "stamping.md").read_text(encoding="utf-8")
    for name in _stampable_templates():
        assert name in skill, "%s is carried but never named in SKILL.md" % name
        assert name in stamping, "%s has no REPO SPECIFICS schema in stamping.md" % name


# ---- Task 5: section 9 deterministic scenarios ---------------------------


def test_sync_scenario_preserves_specifics_against_newer_template():
    stamped = (
        "# v1 body\n\n" + BEGIN + "\nVERSION HOMES: package.json\nMONOREPO: fixed\n" + END + "\n"
    )
    newer = "# v2 body with new guidance\n\n" + BEGIN + "\n<placeholder>\n" + END + "\n"
    merged = lib.preserve_repo_specifics(stamped, newer)
    assert "v2 body with new guidance" in merged
    assert "VERSION HOMES: package.json" in merged and "MONOREPO: fixed" in merged
    assert "<placeholder>" not in merged


def test_sync_refuses_on_each_malformed_shape():
    for bad in ["no block", BEGIN + "\nx\n", "x\n" + END, _stamped("\na\n") + BEGIN + END]:
        with pytest.raises(lib.MarkerError):
            lib.preserve_repo_specifics(bad, _stamped("\nx\n"))


def test_predecessor_retire_scenario(tmp_path):
    claude = tmp_path / ".claude"
    _seed(
        claude,
        "skills/docs-sync/SKILL.md",
        "Keep README and docs/ in sync; fix documentation drift.",
    )
    found = lib.find_predecessors(claude)
    assert [f["name"] for f in found] == ["docs-sync"] and found[0]["kind"] == "docs"


# ---- Phase C: content skill bodies ---------------------------------------

CLR = ONBOARD / "templates" / "changelog-release" / "SKILL.md"
UPD = ONBOARD / "templates" / "update-docs" / "SKILL.md"
SKILL = ONBOARD / "SKILL.md"
RUBRIC = ONBOARD / "references" / "rubric.md"
DETECT = ONBOARD / "references" / "detection.md"
STAMPING = ONBOARD / "references" / "stamping.md"
DOCSIA = ONBOARD / "templates" / "docs-ia"


def _region(path):
    # Return ONLY the authored template body: strip the YAML frontmatter and the
    # provenance header comment, so content assertions test the real rules rather
    # than boilerplate (the provenance line itself mentions "REPO SPECIFICS").
    before, _inner, _after = lib.parse_regions(path.read_text(encoding="utf-8"))
    body = before.split("<!-- stamped by onboard-repo", 1)[0]
    if body.startswith("---"):
        body = body.split("---", 2)[-1]
    return body


def _norm(path):
    # lowercase, strip Markdown emphasis/code markers, and collapse all
    # whitespace, so a rule still matches whether it wraps across a line or is
    # bolded/inline-coded (reflow- and markup-robust content assertions).
    body = _region(path).lower()
    for ch in ("*", "_", "`"):
        body = body.replace(ch, "")
    return " ".join(body.split())


def test_changelog_release_body_pins_key_rules():
    t = _norm(CLR)
    assert "keep a changelog" in t and "semver" in t
    assert "topmost" in t and "git tag" in t and "initial commit" in t
    assert "cite-or-drop" in t or "cite or drop" in t
    assert "[unreleased]" in t and "verbatim" in t
    assert "confirm" in t
    assert "feat" in t and "breaking" in t
    assert "0.0.z" in t and "0.y.z" in t
    assert "repo specifics" in t
    assert "compare" in t and ("dead link" in t or "unless" in t)
    assert "dash" in t or "punctuation" in t
    assert "stage" in t and ("do not commit" in t or "never commit" in t)


def test_changelog_release_body_pins_calver_rules():
    # CalVer is an opt-in scheme next to SemVer, never a replacement: an absent bake
    # must still mean SemVer, and the CalVer branch must carry the rules that keep a
    # date-based version installable (npm/Cargo reject two-part and leading-zero parts).
    t = _norm(CLR)
    assert "bakes no versioning scheme, the scheme is semver" in t
    assert "calver" in t and "the date decides" in t
    assert "counter" in t and "same day" in t
    assert "leading zero" in t and "two-part" in t
    assert "deploy notes" in t
    assert "versioning scheme" in STAMPING.read_text(encoding="utf-8").lower()
    # The skill stages and never commits, so the date can't come from a commit; and
    # baseline detection must read CalVer headings and unprefixed tags, not x.y.z/v<v>.
    assert "no release commit exists yet" in t
    assert "## [<version>]" in t and "chore(release): <tag>" in t
    # The format check must run outside a JS project: no `require('semver')`.
    detect = DETECT.read_text(encoding="utf-8")
    assert "require('semver')" not in detect and "re.fullmatch" in detect
    # A date alone never cuts a release, the counter follows a tag-only baseline too,
    # and a breaking change is called out under both schemes.
    assert "cut a release only when the operator asks for one" in t
    assert "last release (§1, heading, tag or version home)" in t
    assert "else, for calver, the version the baked version homes hold" in t
    assert "in any format, a rendered version that already exists" in t
    assert "never reuse a version" in t
    assert "both schemes: call breaking changes out" in t
    # The clock is read in the bake's zone, from either shell.
    raw = CLR.read_text(encoding="utf-8")
    assert "Bash(date:*)" in raw and "PowerShell(Get-Date:*)" in raw


def test_changelog_release_body_pins_github_release_rules():
    # A GitHub Release is an opt-in bake (default none), and the skill never
    # publishes one itself: `ci` names the workflow that does, `manual` prints the
    # command. Either way the version block must read as standalone release notes.
    t = _norm(CLR)
    assert "github release (baked; default: none)" in t
    assert "standalone release notes" in t
    assert "never create the tag or the release yourself" in t
    assert "gh release create" in t
    assert "ci" in t and "manual" in t
    stamping = STAMPING.read_text(encoding="utf-8").lower()
    assert "github release:" in stamping


def test_changelog_release_still_one_region_and_not_intent_only():
    raw = CLR.read_text(encoding="utf-8")
    lib.parse_regions(raw)
    assert "disable-model-invocation" not in raw


def test_update_docs_body_pins_key_rules():
    t = _norm(UPD)
    assert "readme" in t and "claude.md" in t and "docs/" in t
    assert "changelog" in t and "never" in t
    assert "set of" in t and "source" in t
    assert "bootstrap" in t and ("cap" in t or "suppress" in t)
    assert "package.json" in t and ".env" in t
    assert "route" in t and ("report-only" in t or "report only" in t or "baked" in t)
    assert "applies edits by default" in t and (
        "--dry-run" in t or "dry-run" in t or "dry run" in t
    )
    assert "pointer" in t
    assert "begin generated" in t
    assert "diataxis" in t or "diátaxis" in t
    assert "200" in t or "300" in t
    assert "link" in t and ("lychee" in t or "markdown-link-check" in t or "link check" in t)
    assert "code wins" in t and "file:line" in t
    assert "data" in t and "instruction" in t


def test_update_docs_still_one_region_and_not_intent_only():
    raw = UPD.read_text(encoding="utf-8")
    lib.parse_regions(raw)
    assert "disable-model-invocation" not in raw


def test_skills_own_disjoint_surfaces():
    clr = _norm(CLR)
    upd = _norm(UPD)
    assert "never" in upd and "changelog" in upd
    assert "readme" not in clr.replace("keep a changelog", "")


def test_both_templates_parse_after_authoring():
    for p in (CLR, UPD):
        before, inner, _after = lib.parse_regions(p.read_text(encoding="utf-8"))
        assert before.strip().startswith("---")  # frontmatter intact
        assert "onboard-repo fills this in" in inner or inner.strip() != ""


# ---- Task 9: docs-IA references, seeds, IA-aware template, SKILL prose -----


def test_rubric_defines_four_tiers():
    t = RUBRIC.read_text(encoding="utf-8").lower()
    for tier in ("consumer", "technical", "decision", "historical"):
        assert tier in t
    assert "docs/manual" in t and "docs/internals" in t
    assert "docs/adr" in t and "docs/archive" in t


def test_detection_covers_ia_shape():
    t = DETECT.read_text(encoding="utf-8").lower()
    assert "docs/manual" in t and "rubric.md" in t


def test_docs_ia_seeds_exist_with_content():
    names = [
        "AGENTS.md",
        "CLAUDE.md",
        "README.md",
        "docs-README.md",
        "docs-manual-README.md",
        "internals-README.md",
        "ADR-TEMPLATE.md",
        "docs-archive-README.md",
    ]
    for n in names:
        p = DOCSIA / n
        assert p.is_file(), f"missing seed {n}"
        assert p.stat().st_size > 0, f"empty seed {n}"
    # docs-README links each tier dir that scaffold creates — the internals link
    # must have a seed behind it (review C4), else it 404s after the first commit.
    docs_readme = (DOCSIA / "docs-README.md").read_text(encoding="utf-8")
    assert "internals/" in docs_readme
    assert "@AGENTS.md" in (DOCSIA / "CLAUDE.md").read_text(encoding="utf-8")
    assert "markdownlint-disable-file MD029" in (DOCSIA / "docs-manual-README.md").read_text(
        encoding="utf-8"
    )


def test_update_docs_template_is_ia_present_based():
    t = _norm(UPD)
    assert "docs/manual" in t and "docs/internals" in t
    assert "docs/adr" in t and "docs/archive" in t
    assert "agents.md" in t
    assert "present-based" in t or "gate each" in t or "prerequisite" in t
    assert "absent" in t or "lacks" in t
    assert "docs voice" in t or "docs-voice" in t
    assert "diataxis" in t or "diátaxis" in t
    assert "200" in t or "300" in t
    # partial-IA note (review M4) + apply-by-default safety carries (review S1):
    assert "partial" in t and "missing" in t
    assert "applies edits by default" in t
    assert "uncommitted" in t and "commit" in t  # clean-tree/commit-first advisory


def test_skill_covers_docs_ia_scaffold_and_adoption():
    t = SKILL.read_text(encoding="utf-8").lower()
    assert "docs/manual" in t and "docs/internals" in t
    assert "rubric.md" in t
    assert "move manifest" in t or "move-manifest" in t
    assert "renumber-toc" in t and "rewrite-links" in t
    assert "create-only-missing" in t or "only if absent" in t or "only where absent" in t
    assert ".claude-configs-owned" not in t
    # rollback attributed to the operator + the --sync mode-flip announce (review C6/S1):
    assert "rollback" in t and "operator" in t
    assert "report-first" in t  # the mode-flip announce ("applies by default (was report-first)")


# ---- review fixes: CLI clean-exit + scan resilience + detection widening ---


def test_cli_clean_exit_no_traceback_on_bad_args_and_missing_file(tmp_path):
    cli = _load_cli()
    assert cli.main(["preserve", "only-one-arg"]) == 2  # wrong arg count
    assert cli.main(["find-predecessors"]) == 2  # missing arg
    assert cli.main(["bogus"]) == 2  # unknown command
    assert cli.main(["check-markers", str(tmp_path / "nope.md")]) == 2  # missing file
    assert (
        cli.main(["preserve", str(tmp_path / "a.md"), str(tmp_path / "b.md")]) == 2
    )  # missing files


def test_find_predecessors_survives_broken_entries(tmp_path):
    claude = tmp_path / ".claude"
    _seed(claude, "skills/docs-sync/SKILL.md", "Keep README and docs/ in sync; fix doc drift.")
    (claude / "commands").mkdir(parents=True, exist_ok=True)
    ghost = claude / "commands" / "ghost.md"
    ghost.symlink_to(claude / "commands" / "missing-target.md")  # broken
    (claude / "commands" / "adir.md").mkdir()  # dir named *.md
    found = lib.find_predecessors(claude)  # must not raise
    assert [f["name"] for f in found] == ["docs-sync"]


def test_classify_catches_terse_but_real_changelog():
    # terse, but carries a work-specific (strong) signal
    assert lib.classify_artifact("Update the changelog and bump the version.") == "changelog"
    # changelog.md is a strong signal even in a terse sentence
    assert lib.classify_artifact("Update CHANGELOG.md for this release.") == "changelog"
    # "keep the readme" is a strong signal even in a terse sentence
    assert lib.classify_artifact("Keep the README accurate and up to date.") == "docs"


def test_find_predecessors_scans_namespaced_commands(tmp_path):
    # Claude Code commands can be namespaced in subdirectories.
    claude = tmp_path / ".claude"
    _seed(claude, "commands/release/changelog.md", "Update CHANGELOG.md and bump the version.")
    found = lib.find_predecessors(claude)
    assert [f["name"] for f in found] == ["changelog"] and found[0]["kind"] == "changelog"


def test_classify_ignores_incidental_single_mentions():
    # one incidental weak word is NOT a candidate (spec 7.1 precision)
    assert lib.classify_artifact("Deploy the app; note it in the changelog later.") is None
    assert lib.classify_artifact("See the documentation for CI setup details.") is None
    assert lib.classify_artifact("Scaffold a component and a README stub.") is None
    # but two corroborating weak docs words do qualify
    assert lib.classify_artifact("Update the README and the documentation.") == "docs"


def test_restamp_provenance_sets_version_and_date():
    prov = (
        "<!-- stamped by onboard-repo v1 from claude-configs on <date>. "
        "The template region is regenerated on /onboard-repo --sync "
        "(backup + diff shown first); the REPO SPECIFICS block is preserved. -->"
    )
    out = lib.restamp_provenance(prov, 3, "2026-07-02")
    assert "onboard-repo v3 from claude-configs on 2026-07-02." in out
    assert "<date>" not in out


def test_cli_preserve_restamps_date_on_sync(tmp_path, capsys):
    cli = _load_cli()
    old = tmp_path / "old.md"
    new = tmp_path / "new.md"
    old.write_text("# OLD\n\n" + BEGIN + "\nHOME: pkg.json\n" + END + "\n", encoding="utf-8")
    new.write_text(
        "# NEW\n\n<!-- stamped by onboard-repo v1 from claude-configs on <date>. x. -->\n\n"
        + BEGIN
        + "\nP\n"
        + END
        + "\n",
        encoding="utf-8",
    )
    assert cli.main(["preserve", str(old), str(new), "2026-07-02"]) == 0
    out = capsys.readouterr().out
    assert "HOME: pkg.json" in out  # specifics preserved
    assert "on 2026-07-02." in out and "<date>" not in out  # provenance re-stamped


# ---- Task 6: renumber_toc (docs-IA ToC reflow) ---------------------------


def test_renumber_toc_reflows_list_and_totals():
    toc = (
        "Read the daily-use pages **1 → 2** in order.\n\n"
        "3. [alpha](alpha.md)\n"
        "1. [bravo](bravo.md)\n"
        "9. [charlie](charlie.md)\n\n"
        "→ **Next:** the manual (read 1 → 2).\n"
    )
    out = lib.renumber_toc(toc)
    # list items reflow to 1..3 in document order
    assert "1. [alpha](alpha.md)" in out
    assert "2. [bravo](bravo.md)" in out
    assert "3. [charlie](charlie.md)" in out
    # the seed's real total forms — bold **1 → N** and paren (read 1 → N) — become 3
    assert "**1 → 3**" in out
    assert "(read 1 → 3)" in out
    # idempotent
    assert lib.renumber_toc(out) == out


def test_renumber_toc_no_list_is_noop():
    assert lib.renumber_toc("no list here\n") == "no list here\n"


# ---- Task 7: rewrite_markdown_links (adoption link rewrite) ---------------


def test_rewrite_markdown_links_targets_only():
    text = (
        "See [guide](docs/old.md) and ![img](docs/pic.png).\n"
        "[ref]: docs/old.md\n"
        "```\nopen('docs/old.md')  # code mentions docs/old.md but must NOT change\n```\n"
        "Prose naming docs/old.md inline must NOT change.\n"
    )
    out = lib.rewrite_markdown_links(text, {"docs/old.md": "docs/manual/old.md"})
    assert "[guide](docs/manual/old.md)" in out
    assert "[ref]: docs/manual/old.md" in out
    # the code block and prose mentions are untouched
    assert "open('docs/old.md')" in out
    assert "Prose naming docs/old.md inline" in out
    # image with a non-moved target is untouched
    assert "![img](docs/pic.png)" in out


def test_rewrite_markdown_links_empty_moves_is_noop():
    t = "[x](a.md)\n"
    assert lib.rewrite_markdown_links(t, {}) == t


def test_rewrite_markdown_links_prefix_collision():
    # Moving a.md must NOT touch a.md.bak (old path is a strict prefix of another
    # real link target — the case a naive str.replace WOULD corrupt).
    out = lib.rewrite_markdown_links("[x](a.md) [y](a.md.bak)\n", {"a.md": "docs/a.md"})
    assert "](docs/a.md)" in out
    assert "](a.md.bak)" in out
    assert "](docs/a.md.bak)" not in out


def test_rewrite_markdown_links_anchor_preserved():
    out = lib.rewrite_markdown_links("[x](old.md#sec)\n", {"old.md": "new.md"})
    assert "](new.md#sec)" in out


def test_renumber_toc_skips_fenced_code_block():
    # A numbered list inside a fence is neither renumbered nor counted, and the
    # total reflects only the real ToC items (review I-1).
    toc = (
        "Read pages 1 → 2 in order.\n\n"
        "1. [a](a.md)\n2. [b](b.md)\n\n"
        "```sh\n5. do this\n6. do that\n```\n"
    )
    out = lib.renumber_toc(toc)
    assert "1 → 2 in order" in out  # total counts only the 2 real items
    assert "5. do this" in out and "6. do that" in out  # fence untouched


def test_renumber_toc_leaves_unrelated_prose_totals():
    # A prose "1 to N" that is not a ToC total must not be rewritten (review I-2).
    text = "Backups run 1 to 2 times daily.\n\n1. [a](a.md)\n2. [b](b.md)\n3. [c](c.md)\n"
    out = lib.renumber_toc(text)
    assert "1 to 2 times daily" in out


def test_renumber_toc_leaves_prose_step_ranges():
    # Prose "1 to N" followed by period/word — not ToC totals — stay put (review H1).
    for prose in (
        "Follow steps 1 to 7. Then reboot.",
        "See items 1 to 5 in the appendix.",
        "Supports 1 to 8 pages of history.",
    ):
        text = prose + "\n\n1. [a](a.md)\n2. [b](b.md)\n"
        assert prose in lib.renumber_toc(text), f"prose rewritten: {prose!r}"


def test_renumber_toc_rewrites_real_seed_total_forms():
    # The bold and paren total forms the manual-README seed uses ARE rewritten to N.
    bold = "pages **1 → 9** in order\n\n1. [a](a.md)\n2. [b](b.md)\n"
    assert "**1 → 2**" in lib.renumber_toc(bold)
    paren = "(read 1 → 9)\n\n1. [a](a.md)\n2. [b](b.md)\n3. [c](c.md)\n"
    assert "(read 1 → 3)" in lib.renumber_toc(paren)


def test_renumber_toc_unclosed_fence_to_eof():
    # An UNCLOSED fence runs to EOF (CommonMark) — its items are not renumbered
    # or counted (review m9).
    text = "1. [a](a.md)\n2. [b](b.md)\n\n```sh\n5. do this\n6. do that\n"
    out = lib.renumber_toc(text)
    assert "5. do this" in out and "6. do that" in out


def test_seed_manual_readme_total_heals_to_real_count():
    # Integration (review C1): the shipped seed ships DIGIT totals (1 → 0), so once
    # real page links are added, renumber_toc maintains every total to the count —
    # it must NOT stay frozen at a literal N.
    seed = (DOCSIA / "docs-manual-README.md").read_text(encoding="utf-8")
    assert "→ N" not in seed and "→ 0" in seed  # seed uses a digit, not the letter N
    filled = seed.replace(
        "{{TODO: numbered 1..N page links, grouped}}",
        "3. [a](a.md)\n1. [b](b.md)\n5. [c](c.md)",
    )
    out = lib.renumber_toc(filled)
    assert "**1 → 3**" in out  # intro bold total heals to 3
    assert "(read 1 → 3)" in out  # section-heading paren total heals to 3
    assert "1→3 reading order" in out  # MD029 comment heals to 3
    assert "1. [a](a.md)" in out and "2. [b](b.md)" in out and "3. [c](c.md)" in out


def test_renumber_toc_crlf_safe():
    # A CRLF-closed fence still closes; items after it renumber (review C2).
    crlf = "```\r\ncode\r\n```\r\n\r\n1. [a](a.md)\r\n5. [b](b.md)\r\n9. [c](c.md)\r\n"
    out = lib.renumber_toc(crlf)
    assert "1. [a](a.md)" in out and "2. [b](b.md)" in out and "3. [c](c.md)" in out


def test_renumber_toc_leaves_paren_prose_range():
    # A bare "(1 to N)" / "(1 → N)" prose range next to a list is NOT a ToC total
    # (review C1 over-match).
    for prose in ("the range (1 to 5) of values", "interval (1 → 5) inclusive"):
        text = prose + "\n\n1. [a](a.md)\n2. [b](b.md)\n"
        assert prose in lib.renumber_toc(text), f"prose rewritten: {prose!r}"


def test_rewrite_markdown_links_titled_and_angle_targets():
    # Titled, angle-bracket, and query link targets rewrite (review C3).
    text = '[a](old.md "t") [b](<old.md>) [c](old.md?v=1) [d](old.md.bak)\n'
    out = lib.rewrite_markdown_links(text, {"old.md": "new.md"})
    assert '[a](new.md "t")' in out
    assert "[b](<new.md>)" in out
    assert "[c](new.md?v=1)" in out
    assert "[d](old.md.bak)" in out  # prefix-collision still safe


def test_adoption_pipeline_over_fixture():
    # Integration: fill a manual index with a real ToC, run renumber, then rewrite
    # a moved link — the two deterministic seams chained as adoption uses them.
    toc = "Read pages **1 → 9** in order.\n\n5. [alpha](alpha.md)\n1. [bravo](bravo.md)\n"
    renum = lib.renumber_toc(toc)
    assert "**1 → 2**" in renum
    assert "1. [alpha](alpha.md)" in renum and "2. [bravo](bravo.md)" in renum
    moved = lib.rewrite_markdown_links(renum, {"alpha.md": "getting-started/alpha.md"})
    assert "[alpha](getting-started/alpha.md)" in moved
    assert "[bravo](bravo.md)" in moved


def test_templates_provenance_version_matches_template_version():
    # The stamped provenance version must equal TEMPLATE_VERSION (review M5).
    # Discovered, not listed: a new template must not escape this silently.
    for name in _stampable_templates():
        p = ONBOARD / "templates" / name / "SKILL.md"
        raw = p.read_text(encoding="utf-8")
        assert f"stamped by onboard-repo v{lib.TEMPLATE_VERSION} " in raw, p


def test_stamping_defines_docs_voice_field():
    # The docs-voice bake lives in stamping.md's update-docs schema (review m13).
    t = (ONBOARD / "references" / "stamping.md").read_text(encoding="utf-8").lower()
    assert "docs voice" in t


# ---- Task 8: move manifest + template version ----------------------------


def test_move_manifest_roundtrips():
    pairs = [["docs/old.md", "docs/manual/old.md"], ["a.md", "docs/archive/a.md"]]
    dirs = ["docs/manual", "docs/archive"]
    text = lib.write_move_manifest(pairs, dirs)
    got_pairs, got_dirs = lib.read_move_manifest(text)
    assert got_pairs == pairs
    assert got_dirs == dirs


def test_template_version_is_three():
    assert lib.TEMPLATE_VERSION == 3


# ---- Phase 1: heading_slugs -------------------------------------------------


def _slugs_of(headings):
    md = "\n".join("# " + h for h in headings) + "\n"
    return lib.heading_slugs(md)


def test_heading_slugs_dedup_both_branches():
    # github-slugger: track ALL emitted slugs, bump -N until free.
    assert _slugs_of(["dup", "dup-1", "dup"]) == ["dup", "dup-1", "dup-2"]
    assert _slugs_of(["dup", "dup", "dup-1"]) == ["dup", "dup-1", "dup-1-1"]


def test_heading_slugs_keeps_underscore_and_unicode():
    assert _slugs_of(["Hello_World", "Café", "日本語"]) == ["hello_world", "café", "日本語"]


def test_heading_slugs_spaces_become_dashes_no_collapse():
    assert _slugs_of(["A B  C"]) == ["a-b--c"]  # github-slugger does NOT collapse runs


def test_heading_slugs_skips_fenced_and_setext_documented():
    text = "# Real\n\n```\n# Not A Heading\n```\n"
    assert lib.heading_slugs(text) == ["real"]  # fenced '#' ignored
    # setext headings are a documented non-parse:
    assert lib.heading_slugs("Title\n=====\n") == []


def test_heading_slugs_crlf_and_trailing_hashes():
    assert lib.heading_slugs("# Alpha #\r\n") == ["alpha"]


# ---- Phase 1: table_cell_errors ------------------------------------------------


def test_table_cell_errors_clean_and_spaced_delimiter():
    assert lib.table_cell_errors("| a | b |\n| --- | --- |\n| 1 | 2 |\n") == []
    # per-cell strip is REQUIRED: a spaced '| --- |' must still be a delimiter row
    assert lib.table_cell_errors("| a | b |\n|  ---  |  :---:  |\n| 1 | 2 |\n") == []


def test_table_cell_errors_code_span_pipe_is_error():
    # `x|y` in a body cell splits into an extra cell (GFM does NOT exempt backtick
    # spans) -> more cells than header -> error.
    res = lib.table_cell_errors("| a | b |\n| --- | --- |\n| `x|y` | 2 |\n")
    assert [(r[1], r[2], r[3]) for r in res] == [("error", 3, 2)]


def test_table_cell_errors_colon_pipe_value_is_error():
    res = lib.table_cell_errors("| a | b |\n| --- | --- |\n| :|: | 2 |\n")
    assert [r[1] for r in res] == ["error"]


def test_table_cell_errors_short_row_is_warn():
    res = lib.table_cell_errors("| a | b |\n| --- | --- |\n| 1 |\n")
    assert [r[1] for r in res] == ["warn"]


def test_table_cell_errors_escaped_pipe_not_split():
    # An escaped \| inside a cell is ONE cell, not a split (GFM).
    assert lib.table_cell_errors("| a | b |\n| --- | --- |\n| x \\| y | 2 |\n") == []


def test_table_cell_errors_ignores_fenced_and_reports_lineno():
    assert lib.table_cell_errors("```\n| a | b |\n| --- |\n```\n") == []
    # lineno points at the offending BODY row (1-based); the code-span pipe
    # overflows the 2-column header to 3 cells -> error.
    res = lib.table_cell_errors("intro\n\n| a | b |\n| --- | --- |\n| `x|y` | z |\n")
    assert res and res[0][0] == 5


# ---- Phase 1: iter_markdown_links ------------------------------------------


def test_iter_markdown_links_inline_image_refdef():
    text = (
        "See [guide](a.md) and ![pic](img/p.png).\n"
        "[ref]: b.md#sec\n"
        "```\n[x](should-not-appear.md)\n```\n"
    )
    got = lib.iter_markdown_links(text)
    targets = [t for (_d, t, _ln) in got]
    assert "a.md" in targets and "img/p.png" in targets and "b.md#sec" in targets
    assert "should-not-appear.md" not in targets  # fenced


def test_iter_markdown_links_angle_target_with_space():
    got = lib.iter_markdown_links("[a](<my file.md>)\n")
    assert ("a", "my file.md", 1) in [(d, t, ln) for (d, t, ln) in got]


def test_iter_markdown_links_reports_line_numbers():
    got = lib.iter_markdown_links("line1\n\n[a](x.md)\n")
    assert any(t == "x.md" and ln == 3 for (_d, t, ln) in got)


def test_iter_markdown_links_lineno_after_fence():
    # a link in a prose segment that FOLLOWS a fence must report the true line.
    text = "intro para\n\n```\ncode\n```\n\n[a](x.md)\n"
    got = lib.iter_markdown_links(text)
    assert any(t == "x.md" and ln == 7 for (_d, t, ln) in got)


# ---- Phase 1: rebase_relative_links ----------------------------------------


def test_rebase_co_move_sibling_unchanged():
    # page docs/a.md -> docs/manual/a.md, sibling b.md co-moved: link text same.
    moves = {"docs/a.md": "docs/manual/a.md", "docs/b.md": "docs/manual/b.md"}
    out = lib.rebase_relative_links(
        "[b](b.md) [b2](b.md#sec)\n", "docs/a.md", "docs/manual/a.md", moves
    )
    assert out == "[b](b.md) [b2](b.md#sec)\n"


def test_rebase_target_only_move():
    out = lib.rebase_relative_links(
        "[b](b.md)\n", "docs/a.md", "docs/a.md", {"docs/b.md": "docs/manual/b.md"}
    )
    assert out == "[b](manual/b.md)\n"


def test_rebase_page_only_move_escapes_up():
    out = lib.rebase_relative_links(
        "[b](b.md)\n", "docs/a.md", "docs/manual/a.md", {"docs/a.md": "docs/manual/a.md"}
    )
    assert out == "[b](../b.md)\n"


def test_rebase_leaves_anchor_and_external():
    out = lib.rebase_relative_links(
        "[x](#local) [h](https://z.com) [m](mailto:a@b.c)\n", "docs/a.md", "docs/manual/a.md", {}
    )
    assert out == "[x](#local) [h](https://z.com) [m](mailto:a@b.c)\n"


def test_rebase_skips_fenced_links():
    text = "[b](b.md)\n\n```\n[b](b.md)\n```\n"
    out = lib.rebase_relative_links(
        text, "docs/a.md", "docs/manual/a.md", {"docs/a.md": "docs/manual/a.md"}
    )
    assert "[b](../b.md)" in out and "```\n[b](b.md)\n```" in out  # fenced copy untouched


def test_rebase_page_only_move_spaced_angle_target():
    # M2: a spaced <angle> relative link in a page-only move is rebased and stays
    # angle-wrapped — the old `[^)>\s]+` capture stopped at the space and dangled.
    out = lib.rebase_relative_links(
        "[b](<my file.md>)\n", "docs/a.md", "docs/manual/a.md", {"docs/a.md": "docs/manual/a.md"}
    )
    assert out == "[b](<../my file.md>)\n"


# ---- Phase 1: grounding trio -----------------------------------------------


def test_redact_output_boundary_anchored():
    src = "/home/jack/proj\njack ran it\njackson unaffected\nstamp-20260101\n"
    out = lib.redact_output(src, "/home/jack", "jack", "stamp-20260101", [])
    assert "~/proj" in out
    assert "<user> ran it" in out
    assert "jackson unaffected" in out  # NOT mangled
    assert "<stamp>" in out and "stamp-20260101" not in out
    assert "/home/jack" not in out


def test_redact_output_extra_tokens_boundary_only():
    out = lib.redact_output(
        "acme-secret here\nacme-secretary stays\n", "/h", "u", "s", ["acme-secret"]
    )
    assert "<redacted> here" in out
    assert "acme-secretary stays" in out


def test_redact_output_idempotent():
    once = lib.redact_output("/home/jack/x\n", "/home/jack", "jack", "s", [])
    assert lib.redact_output(once, "/home/jack", "jack", "s", []) == once


def test_canonicalize_output_env_free_idempotent():
    c = lib.canonicalize_output("a  \r\nb\t\n\n")
    assert c == "a\nb\n"
    assert lib.canonicalize_output(c) == c


def test_output_subsequence_ok_elision_and_order():
    committed = "line1\nline2\nline3\nline4\n"
    assert lib.output_subsequence_ok("line1\n…\nline4\n", committed) is True
    assert lib.output_subsequence_ok("line1\nline2\n", committed) is True
    assert lib.output_subsequence_ok("line4\nline1\n", committed) is False  # out of order
    assert lib.output_subsequence_ok("not present\n", committed) is False


def test_output_subsequence_ok_hash_ellipsis_token():
    committed = "a\nb\nc\n"
    assert lib.output_subsequence_ok("a\n# ...\nc\n", committed) is True


# ---- Phase 1: shrink_violations --------------------------------------------


def _words(n):
    return " ".join("w%d" % i for i in range(n)) + "\n"


def test_shrink_violations_big_cut_is_error_unless_cleared():
    old = "# H\n\n" + _words(100)
    new = "# H\n\n" + _words(50)  # 50% cut
    assert any(k == "error" for k, _ in lib.shrink_violations(old, new, False))
    assert lib.shrink_violations(old, new, True) == []  # cleared a finding: allowed


def test_shrink_violations_heading_drop_is_warn():
    old = "# Keep\n\n## Dropped\n\n" + _words(40)
    new = "# Keep\n\n" + _words(38)
    res = lib.shrink_violations(old, new, False)
    assert any(k == "warn" and "dropped" in msg.lower() for k, msg in res)


def test_shrink_violations_small_edit_clean():
    old = "# H\n\n" + _words(100)
    new = "# H\n\n" + _words(90)  # 10% cut, no heading loss
    assert lib.shrink_violations(old, new, False) == []


# ---- Phase 2: adoption/loop verbs ------------------------------------------


def test_cli_rebase_links(tmp_path, capsys):
    cli = _load_cli()
    page = _seed(tmp_path, "p.md", "[b](b.md)\n")
    man = _seed(
        tmp_path,
        "moves.json",
        lib.write_move_manifest([["docs/a.md", "docs/manual/a.md"]], ["docs/manual"]),
    )
    rc = cli.main(["rebase-links", str(page), "docs/a.md", "docs/manual/a.md", str(man)])
    assert rc == 0
    assert "[b](../b.md)" in capsys.readouterr().out


def test_cli_shrink_check_error_and_cleared(tmp_path, capsys):
    cli = _load_cli()
    old = _seed(tmp_path, "old.md", "# H\n\n" + " ".join("w%d" % i for i in range(100)) + "\n")
    new = _seed(tmp_path, "new.md", "# H\n\n" + " ".join("w%d" % i for i in range(40)) + "\n")
    assert cli.main(["shrink-check", str(old), str(new)]) == 1
    assert cli.main(["shrink-check", str(old), str(new), "--cleared"]) == 0


def test_cli_redact_boundary_anchored(tmp_path, capsys):
    # I6: the `redact` verb reads a raw capture and writes boundary-anchored,
    # env-parameterized redaction to stdout (never a blind substring).
    cli = _load_cli()
    raw = _seed(
        tmp_path,
        ".onboard-repo-retired/s1/captures-raw/plan.txt",
        "/home/jack/proj\njack ran it\njackson unaffected\nstamp-20260101\n",
    )
    rc = cli.main(
        ["redact", str(raw), "--home", "/home/jack", "--user", "jack", "--stamp", "stamp-20260101"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "~/proj" in out
    assert "<user> ran it" in out
    assert "jackson unaffected" in out  # boundary-safe: jack->jackson NOT mangled
    assert "<stamp>" in out and "stamp-20260101" not in out
    assert "/home/jack" not in out


def test_cli_redact_missing_raw_file_is_exit_2(tmp_path):
    cli = _load_cli()
    assert cli.main(["redact"]) == 2  # missing raw file
    assert cli.main(["redact", str(tmp_path / "nope.txt"), "--home", "/h"]) == 2  # unreadable


# ---- Phase 2: check-docs skeleton ------------------------------------------


def _run_check(cli, capsys, roots, extra=None):
    """Run `check-docs` over `roots` (+ any extra CLI args) and parse stdout's
    SEVERITY\\tCODE\\tfile:lineno\\tdetail lines. Returns (rc, codes, lines)."""
    rc = cli.main(["check-docs"] + list(roots) + list(extra or []))
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln]
    codes = [ln.split("\t")[1] for ln in lines]
    return rc, codes, lines


def test_iter_fenced_blocks_info_and_body():
    blocks = lib.iter_fenced_blocks("intro\n\n```text capture=x\nabc\n```\n")
    assert blocks == [("text capture=x", "abc\n", 3)]


def test_iter_fenced_blocks_unclosed_eof_no_phantom_blank():
    # M1: an UNCLOSED fence to EOF must not gain a spurious trailing blank line
    # from the opener's own '\n' — the body is honest "abc\n", not "abc\n\n".
    assert lib.iter_fenced_blocks("```text\nabc\n") == [("text", "abc\n", 1)]


def test_check_docs_clean_tree_exit_0(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/a.md", "# A\n\nSee [b](b.md).\n")
    _seed(tmp_path, "docs/manual/b.md", "# B\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


def test_check_docs_no_roots_is_usage_exit_2(tmp_path, capsys):
    cli = _load_cli()
    assert cli.main(["check-docs"]) == 2


def test_check_docs_unreadable_captures_is_exit_2(tmp_path):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n")
    rc = cli.main(["check-docs", str(tmp_path / "docs"), "--captures", str(tmp_path / "nope-dir")])
    assert rc == 2


def test_check_docs_malformed_coverage_is_exit_2(tmp_path, capsys):
    # I2: a broken coverage record exits 2 with a coverage-specific message and
    # is NOT routed through the broad "malformed manifest" handler (no traceback).
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n")
    cov = _seed(tmp_path, "docs/.onboard-coverage.json", "{ not valid json at all")
    rc = cli.main(["check-docs", str(tmp_path / "docs"), "--coverage", str(cov)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "malformed coverage record" in err
    assert "Traceback" not in err
    assert "malformed manifest" not in err  # not the manifest handler's message


def test_check_docs_skips_excluded_dirs(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n")
    _seed(tmp_path, "docs/node_modules/x.md", "[dead](does-not-exist.md)\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []  # node_modules never walked


# ---- Phase 2: link + anchor checks -----------------------------------------


def test_check_docs_broken_link_in_roots_is_error(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n[gone](missing.md)\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 1 and "BROKEN_LINK" in codes


def test_check_docs_broken_anchor_is_error(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# Title\n\n[x](#no-such-heading)\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 1 and "BROKEN_ANCHOR" in codes


def test_check_docs_anchor_case_insensitive_ok(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# My Heading\n\n[x](#MY-HEADING)\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


def test_check_docs_link_to_excluded_is_existence_only_warn(tmp_path, capsys):
    cli = _load_cli()
    # link points OUTSIDE the checked root (archive not in roots) and target missing
    _seed(tmp_path, "docs/manual/a.md", "# A\n\n[old](../archive/gone.md#sec)\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs" / "manual")])
    assert rc == 0 and codes == ["BROKEN_LINK"]  # warn, not error; anchor skipped


def test_check_docs_live_link_to_existing_archive_ok(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/a.md", "# A\n\n[old](../archive/note.md)\n")
    _seed(tmp_path, "docs/archive/note.md", "# Note\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs" / "manual")])
    assert rc == 0 and codes == []  # exists on disk -> fine even though out of roots


# ---- Phase 2: table checks -------------------------------------------------


def test_check_docs_malformed_table_is_error(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n| x | y |\n| --- | --- |\n| `a|b` | 2 |\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 1 and "MALFORMED_TABLE" in codes


def test_check_docs_short_row_is_warn(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n| x | y |\n| --- | --- |\n| 1 |\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == ["TABLE_SHORT_ROW"]


# ---- Phase 2: placeholder check --------------------------------------------


def test_check_docs_placeholder_warn_without_coverage(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n{{TODO: write intro}}\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == ["PLACEHOLDER"]  # scaffold-only -> warn


def test_check_docs_placeholder_error_with_coverage(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n{{TODO: write intro}}\n")
    cov = _seed(
        tmp_path,
        "docs/.onboard-coverage.json",
        '[{"surface":"Install","slug":"install","tier":"principal",'
        '"page":"docs/a.md","status":"covered"}]',
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--coverage", str(cov)])
    assert rc == 1 and "PLACEHOLDER" in codes


def test_check_docs_placeholder_ignores_template_files(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/adr/ADR-TEMPLATE.md", "# <title>\n\n{{TODO: context}}\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


# ---- Phase 2: grounding -----------------------------------------------------


def _cap(tmp_path, slug, body):
    return _seed(tmp_path, "docs/.onboard-captures/%s.txt" % slug, body)


def test_check_docs_untagged_output_is_error(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n```text\nFiles to write:\n  ~/.claude/x\n```\n")
    caps = _seed(tmp_path, "docs/.onboard-captures/.keep", "").parent
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--captures", str(caps)])
    assert rc == 1 and "UNTAGGED_OUTPUT" in codes


def test_check_docs_capture_match_is_clean(tmp_path, capsys):
    cli = _load_cli()
    _cap(tmp_path, "plan", "Files to write:\n  ~/.claude/x\n  ~/.claude/y\n")
    _seed(
        tmp_path,
        "docs/a.md",
        "# A\n\n```text capture=plan\nFiles to write:\n…\n  ~/.claude/y\n```\n",
    )
    caps = str(tmp_path / "docs" / ".onboard-captures")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--captures", caps])
    assert rc == 0 and codes == []


def test_check_docs_ungrounded_output_when_line_not_in_capture(tmp_path, capsys):
    cli = _load_cli()
    _cap(tmp_path, "plan", "Files to write:\n  ~/.claude/x\n")
    _seed(tmp_path, "docs/a.md", "# A\n\n```text capture=plan\nTOTALLY INVENTED LINE\n```\n")
    caps = str(tmp_path / "docs" / ".onboard-captures")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--captures", caps])
    assert rc == 1 and "UNGROUNDED_OUTPUT" in codes


def test_check_docs_console_capture_with_output_only_is_verified(tmp_path, capsys):
    # The documented convention puts the COMMAND in a bash fence and its OUTPUT alone in a
    # `console capture=<slug>` fence. console is a shell language, and a shell fence with no `$`
    # prompt reads as a bare command list -- so the capture tag was never read and a tampered
    # capture passed (found in brainiac-pipeline, 2026-10-12). An explicit capture= tag is always
    # verified, whatever the fence's language or shape.
    cli = _load_cli()
    _cap(tmp_path, "plan", "workspace: created x\n")
    _seed(tmp_path, "docs/a.md", "# A\n\n```console capture=plan\nNOT WHAT THE TOOL SAID\n```\n")
    caps = str(tmp_path / "docs" / ".onboard-captures")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--captures", caps])
    assert rc == 1 and "UNGROUNDED_OUTPUT" in codes


def test_check_docs_console_capture_grounded_passes(tmp_path, capsys):
    cli = _load_cli()
    _cap(tmp_path, "plan", "workspace: created x\nworkspace: shallow history\n")
    _seed(tmp_path, "docs/a.md", "# A\n\n```console capture=plan\nworkspace: created x\n```\n")
    caps = str(tmp_path / "docs" / ".onboard-captures")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--captures", caps])
    assert rc == 0 and codes == []


def test_check_docs_code_fence_exempt(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n```python\nprint('hi')\n```\n")
    caps = _seed(tmp_path, "docs/.onboard-captures/.keep", "").parent
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--captures", str(caps)])
    assert rc == 0 and codes == []


def test_check_docs_command_only_block_exempt(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n```bash\n$ ./install.sh --plan\n```\n")
    caps = _seed(tmp_path, "docs/.onboard-captures/.keep", "").parent
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--captures", str(caps)])
    assert rc == 0 and codes == []


def test_check_docs_capturable_illustrative_is_warn(tmp_path, capsys):
    cli = _load_cli()
    _seed(
        tmp_path,
        "docs/a.md",
        "# A\n\n```text illustrative\n$ ls\nfile-a\nfile-b\n```\n",
    )
    caps = _seed(tmp_path, "docs/.onboard-captures/.keep", "").parent
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--captures", str(caps)])
    assert rc == 0 and "CAPTURABLE_ILLUSTRATIVE" in codes


def test_check_docs_shell_fence_command_list_is_not_output(tmp_path, capsys):
    # A bare command list under ```bash is what install docs write constantly. It
    # is not a transcript, so demanding capture=<slug>/illustrative on it would
    # force the author to label authored instructions as captured output.
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n```bash\ndotnet build\ndotnet test\n```\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and "UNTAGGED_OUTPUT" not in codes


def test_check_docs_shell_fence_comments_do_not_read_as_prompts(tmp_path, capsys):
    # `#` opens a shell comment but the prompt regex reads it as a root prompt, so
    # an annotated command list must not be misclassified as a transcript.
    cli = _load_cli()
    _seed(
        tmp_path,
        "docs/a.md",
        "# A\n\n```bash\n# install it\n$ brew install x\n$ brew upgrade x\n```\n",
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and "UNTAGGED_OUTPUT" not in codes


def test_check_docs_shell_fence_command_plus_output_still_needs_provenance(tmp_path, capsys):
    # The case grounding exists for: a command AND what it printed, pasted under a
    # shell fence with no capture=/illustrative tag.
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n```console\n$ ls\nfile-a\nfile-b\n```\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert "UNTAGGED_OUTPUT" in codes


def test_check_docs_source_fences_are_exempt_from_grounding(tmp_path, capsys):
    # A C# snippet or a mermaid diagram is authored illustration, never command
    # output -- it must not be asked to prove provenance.
    cli = _load_cli()
    _seed(
        tmp_path,
        "docs/a.md",
        "# A\n\n```csharp\nvar x = 1;\n```\n\n```mermaid\ngraph TD;\nA-->B;\n```\n",
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and "UNTAGGED_OUTPUT" not in codes


def test_shell_and_code_lang_sets_are_disjoint():
    # A fence tagged shell must reach the prompt test, never the blanket source
    # exemption; an overlap would silently disable grounding for that tag.
    lib_cli = _load_check()
    assert not (lib_cli._CODE_LANGS & lib_cli._SHELL_LANGS)
    for tag in ("sh", "bash", "console", "powershell"):
        assert tag in lib_cli._SHELL_LANGS and tag not in lib_cli._CODE_LANGS


# ---- Phase 2: EMPTY_TIER ----------------------------------------------------


def test_check_docs_empty_tier_warn_without_coverage(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/README.md", "# Manual\n")  # only README, no real pages
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and "EMPTY_TIER" in codes  # warn


def test_check_docs_empty_tier_error_with_principal_null(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/README.md", "# Manual\n")
    cov = _seed(
        tmp_path,
        "docs/.onboard-coverage.json",
        '[{"surface":"Install","slug":"install","tier":"principal",'
        '"page":null,"status":"covered"}]',
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--coverage", str(cov)])
    assert rc == 1 and "EMPTY_TIER" in codes  # principal page null -> error


def test_check_docs_no_empty_tier_when_principal_covered(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/README.md", "# Manual\n")
    _seed(tmp_path, "docs/manual/install.md", "# Install\n\nReal content here.\n")
    cov = _seed(
        tmp_path,
        "docs/.onboard-coverage.json",
        '[{"surface":"Install","slug":"install","tier":"principal",'
        '"page":"docs/manual/install.md","status":"covered"}]',
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--coverage", str(cov)])
    assert rc == 0 and "EMPTY_TIER" not in codes


def test_check_docs_empty_tier_ignores_excluded_manual(tmp_path, capsys):
    # M3: a manual/ under node_modules/ is NOT real content — it must not suppress
    # the no-coverage EMPTY_TIER warn for the genuinely-empty real manual tier.
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/README.md", "# Manual\n")  # only README, no real pages
    _seed(tmp_path, "docs/node_modules/x/manual/y.md", "# Vendored\n\nnot real docs\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and "EMPTY_TIER" in codes  # warn still fires


def test_check_docs_empty_tier_stray_ancestor_page_not_bound(tmp_path, capsys):
    # I1 hardened (S1-C1): a coverage `page` resolving to a real file OUTSIDE the
    # checked roots must NOT be bound; the principal surface still reads as missing
    # (EMPTY_TIER fires). Uses an ABSOLUTE path to a stray one dir above the root —
    # this exercises the `_resolve_coverage_page` fallback branch that an earlier
    # bare-filename test passed vacuously without ever reaching.
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/README.md", "# Manual\n")  # no real principal page
    stray = _seed(tmp_path, "xyzzy-install.md", "# Stray\n\nreal content that must not bind\n")
    cov = _seed(
        tmp_path,
        "docs/.onboard-coverage.json",
        '[{"surface":"Install","slug":"install","tier":"principal",'
        '"page":%s,"status":"covered"}]' % json.dumps(str(stray)),
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--coverage", str(cov)])
    assert rc == 1 and "EMPTY_TIER" in codes  # out-of-root absolute stray is NOT bound


@pytest.mark.skipif(
    sys.platform == "win32" or hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="chmod-based unreadable file not enforced for root or on Windows",
)
def test_check_docs_empty_tier_unreadable_page_degrades_locally(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/README.md", "# Manual\n")
    page = _seed(tmp_path, "docs/manual/install.md", "# Install\n\nReal content here.\n")
    # An unrelated file with a real finding, to prove the run doesn't abort.
    _seed(tmp_path, "docs/a.md", "# A\n\n[gone](missing.md)\n")
    cov = _seed(
        tmp_path,
        "docs/.onboard-coverage.json",
        '[{"surface":"Install","slug":"install","tier":"principal",'
        '"page":"docs/manual/install.md","status":"covered"}]',
    )
    page.chmod(0o000)
    try:
        rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--coverage", str(cov)])
    finally:
        page.chmod(0o644)
    assert rc == 1
    assert "EMPTY_TIER" in codes  # unreadable page degrades to a finding, not a crash
    assert "BROKEN_LINK" in codes  # other files' findings are preserved


# ---- Phase 2: forbidden token + unresolved command --------------------------


def test_check_docs_forbidden_token_opt_in_error(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n```\nAKIAsecret in a fence\n```\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--forbidden", "AKIAsecret"])
    assert rc == 1 and "FORBIDDEN_TOKEN" in codes


def test_check_docs_forbidden_default_empty_is_noop(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\nnothing forbidden here\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and "FORBIDDEN_TOKEN" not in codes


def test_check_docs_unresolved_command_skipped_without_authoritative_surface(tmp_path, capsys):
    # UNRESOLVED_COMMAND is spec-4.2's HONEST SKIP: with no committed authoritative
    # --help/usage snapshot, a documented command is deliberately NOT flagged. Pinned
    # at the unit level too (not just the pipeline), so this asserts
    # _check_unresolved_command's documented contract (always []) rather than passing
    # by accident. When the authoritative-snapshot path is implemented, REPLACE this
    # with a positive UNRESOLVED_COMMAND -> exit 1 case (seed <slug>-help.txt + a doc
    # naming a verb/flag absent from it).
    cli = _load_cli()
    chk = _load_check()
    doc = _seed(tmp_path, "docs/a.md", "# A\n\nRun `mytool deploy`; see `mytool --frob`.\n")
    caps = _seed(tmp_path, "docs/.onboard-captures/.keep", "").parent
    # unit contract: deliberately inert regardless of documented commands + a captures dir
    assert chk._check_unresolved_command(doc, doc.read_text(encoding="utf-8"), str(caps)) == []
    # pipeline: no UNRESOLVED_COMMAND finding; run stays clean
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--captures", str(caps)])
    assert rc == 0 and "UNRESOLVED_COMMAND" not in codes


# ---- M7: coverage-gap tests ------------------------------------------------


def test_check_docs_cross_file_broken_anchor_precise(tmp_path, capsys):
    # a link to a MISSING heading in another in-roots page errors; the sibling
    # link to a REAL heading in the same target is clean.
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n[bad](b.md#missing) and [good](b.md#real)\n")
    _seed(tmp_path, "docs/b.md", "# B\n\n## Real\n")
    rc, codes, lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 1
    anchors = [ln for ln in lines if "BROKEN_ANCHOR" in ln]
    assert len(anchors) == 1  # only the missing one
    assert "b.md#missing" in anchors[0] and "b.md#real" not in anchors[0]


def test_check_docs_excludes_skill_templates(tmp_path, capsys):
    # a dead link inside .../skills/<x>/templates/** (pre-stamp scaffold) under a
    # checked root is excluded — no finding.
    cli = _load_cli()
    _seed(tmp_path, "docs/skills/x/templates/foo.md", "# Foo\n\n[dead](does-not-exist.md)\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


def test_check_docs_capture_missing_slug_file_is_ungrounded(tmp_path, capsys):
    # a fence tagged capture=<slug> with an existing captures dir but no matching
    # <slug>.txt is ungrounded (the capture it cites does not exist).
    cli = _load_cli()
    caps = _seed(tmp_path, "docs/.onboard-captures/.keep", "").parent
    _seed(
        tmp_path,
        "docs/a.md",
        "# A\n\n```text capture=missing-slug\nsome captured-looking output\n```\n",
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--captures", str(caps)])
    assert rc == 1 and "UNGROUNDED_OUTPUT" in codes


# ---- Phase 3: prose hardening (SKILL.md, docs-IA seeds, references) --------


def test_skill_frontmatter_grants_task_for_reviewer():
    body = (ONBOARD / "SKILL.md").read_text(encoding="utf-8")
    fm = body.split("---", 2)[1]
    assert "Task" in fm  # reviewer grant (spec 2.2 / 6)


def test_docs_ia_author_later_seeds_use_todo_sentinel():
    manual = (DOCSIA / "docs-manual-README.md").read_text(encoding="utf-8")
    assert "{{TODO:" in manual
    assert "<numbered 1..N page links, grouped>" not in manual
    # substitute-now token stays angle-bracketed:
    assert "<repo>" in manual


def test_docs_ia_seeds_pass_check_docs_as_scaffold(tmp_path, capsys):
    # the shipped seeds, dropped as a pure scaffold (no coverage record), must be
    # PLACEHOLDER-warn (not error) and otherwise clean. The docs-IA scaffold
    # creates sibling tier dirs together, so seed them (even empty) alongside
    # manual/ -- this must NOT rely on downgrading in-roots BROKEN_LINK
    # severity for directory-only references (that contract stays an error).
    cli = _load_cli()
    for name, rel in (
        ("docs-manual-README.md", "docs/manual/README.md"),
        ("docs-README.md", "docs/README.md"),
    ):
        _seed(tmp_path, rel, (DOCSIA / name).read_text(encoding="utf-8"))
    for sibling in ("internals", "adr", "archive"):
        (tmp_path / "docs" / sibling).mkdir(parents=True, exist_ok=True)
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0  # warnings only (PLACEHOLDER without coverage)
    assert "PLACEHOLDER" in codes  # the {{TODO}} sentinels warn (not error) as a scaffold
    # the scaffold emits exactly these warn-level codes and nothing error-level:
    assert set(codes) <= {"PLACEHOLDER", "EMPTY_TIER", "BROKEN_LINK"}


def test_skill_documents_authoring_loop_and_reviewer():
    t = (ONBOARD / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "check-docs" in t  # mechanical gate invoked
    assert "capture=" in t and "illustrative" in t  # provenance tags
    assert ".onboard-captures" in t and ".onboard-coverage.json" in t
    assert "principal" in t and ("niche" in t and "deferred" in t)
    assert "--no-review" in t and "reviewer" in t  # default-on reviewer + opt-out
    assert "shrink-check" in t  # loop guard invoked
    assert "3 rounds" in t or "three rounds" in t  # bounded loop
    assert "git restore" in t and "git clean" in t  # per-file give-up rollback
    assert "captures-raw" in t and "redact" in t  # raw-staging path + redact verb (I6/§4.3)


def test_detection_defines_surface_enumerator_and_tiers():
    t = DETECT.read_text(encoding="utf-8").lower()
    assert "principal" in t and "niche" in t
    assert "onboard-coverage.json" in t
    assert "operator override" in t or "override" in t


def test_skill_documents_claude_to_agents_and_link_order():
    t = (ONBOARD / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "@agents.md" in t  # wholesale CLAUDE stub
    assert "cat agents.md" in t  # additive append via the real `cat AGENTS.md addition` mechanic
    assert "no-op" in t or "already on the convention" in t
    assert "rewrite-links" in t and "rebase-links" in t
    # order is load-bearing: rewrite (into moved files) BEFORE rebase (out of pages)
    assert t.index("rewrite-links") < t.index("rebase-links")


def test_references_state_show_dont_tell_and_provenance_convention():
    stamping = (ONBOARD / "references" / "stamping.md").read_text(encoding="utf-8").lower()
    assert "show" in stamping and "tell" in stamping  # show-don't-tell
    assert "capture=" in stamping or "provenance tag" in stamping
    rubric = (ONBOARD / "references" / "rubric.md").read_text(encoding="utf-8").lower()
    assert "principal" in rubric and "niche" in rubric
    assert "parity" in rubric or "platform" in rubric


def test_update_docs_template_has_show_dont_tell_rule():
    t = _norm(UPD)
    assert "show" in t and "tell" in t


# ---- review session 1: gate hardening (coverage shape, non-str page, dedup) ----


@pytest.mark.parametrize(
    "bad", ["5", '"hello"', '["junk"]', '{"a": 1}', '[{"tier":"principal"},"junk"]']
)
def test_check_docs_malformed_coverage_shape_is_exit_2(tmp_path, capsys, bad):
    # valid JSON but NOT a list-of-objects must exit 2 cleanly (no traceback),
    # not blow up with TypeError/AttributeError deeper in the gate.
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n")
    cov = _seed(tmp_path, "docs/.onboard-coverage.json", bad)
    rc = cli.main(["check-docs", str(tmp_path / "docs"), "--coverage", str(cov)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "Traceback" not in err


def test_check_docs_non_string_page_is_empty_tier(tmp_path, capsys):
    # a principal row whose `page` is a non-string JSON value is treated as missing
    # (EMPTY_TIER), never a pathlib.Path(int) crash.
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/README.md", "# Manual\n")
    cov = _seed(
        tmp_path,
        "docs/.onboard-coverage.json",
        '[{"surface":"Install","slug":"install","tier":"principal","page":123,"status":"covered"}]',
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--coverage", str(cov)])
    assert rc == 1 and "EMPTY_TIER" in codes


def test_check_docs_dedups_repeated_file_roots(tmp_path, capsys):
    # the same file root passed twice (e.g. an index doc listed alongside <index>)
    # is scanned ONCE — findings are not doubled.
    cli = _load_cli()
    # a same-file broken anchor is a deterministic ERROR (independent of roots),
    # so doubling would show up as count 2.
    doc = _seed(tmp_path, "AGENTS.md", "# A\n\n[x](#no-such-heading)\n")
    rc, codes, _ = _run_check(cli, capsys, [str(doc), str(doc)])
    assert rc == 1 and codes.count("BROKEN_ANCHOR") == 1


def test_rebase_relative_links_refuses_absolute_moves_value():
    # an absolute `moves` value would make posixpath.relpath cwd-dependent; the
    # helper must leave the link untouched instead (purity).
    out = lib.rebase_relative_links(
        "[b](b.md)\n", "docs/a.md", "docs/x.md", {"docs/b.md": "/abs/z.md"}
    )
    assert out == "[b](b.md)\n"


# ---- review session 2: resolver hardening + O(n) scanning + honest redaction --


@pytest.mark.parametrize(
    "page",
    [
        "docs/.onboard-coverage.json",  # the coverage record itself
        "docs/manual/README.md",  # the manual nav index (readme stem, not content)
        "README.md",  # the repo landing page (a file root, not a manual page)
    ],
)
def test_check_docs_principal_page_must_be_real_manual_page(tmp_path, capsys, page):
    # H1: a principal `page` that resolves to an in-roots file which is NOT a
    # genuine authored manual page (the coverage JSON, the manual nav index, or
    # the repo README) still reads as EMPTY_TIER — merely being in-roots is not
    # enough; the page must be one _manual_real_pages would yield.
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/README.md", "# Manual\n")  # nav only, no real page
    _seed(tmp_path, "README.md", "# Repo\n\nlanding content\n")
    cov = _seed(
        tmp_path,
        "docs/.onboard-coverage.json",
        '[{"surface":"Install","slug":"install","tier":"principal",'
        '"page":%s,"status":"covered"}]' % json.dumps(page),
    )
    roots = [str(tmp_path / "docs"), str(tmp_path / "README.md")]
    rc, codes, _ = _run_check(cli, capsys, roots, ["--coverage", str(cov)])
    assert rc == 1 and "EMPTY_TIER" in codes


def test_check_docs_pathological_page_value_is_finding_not_crash(tmp_path, capsys):
    # H2: a principal `page` whose value cannot even be stat'd (a 20000-char
    # string -> ENAMETOOLONG) must be a FINDING (EMPTY_TIER, rc 1), never a fatal
    # usage-2 that discards every other finding. A second surface's real broken
    # link still surfaces in the same run.
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/README.md", "# Manual\n")
    _seed(tmp_path, "docs/a.md", "# A\n\n[gone](missing.md)\n")  # real finding elsewhere
    cov = _seed(
        tmp_path,
        "docs/.onboard-coverage.json",
        '[{"surface":"Install","slug":"install","tier":"principal",'
        '"page":%s,"status":"covered"}]' % json.dumps("a" * 20000),
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--coverage", str(cov)])
    assert rc == 1
    assert "EMPTY_TIER" in codes  # the bad page value is a finding
    assert "BROKEN_LINK" in codes  # NOT discarded by a fatal exit 2


def test_iter_markdown_links_lineno_after_fence_and_many_lines():
    # M-DoS: guards the incremental line-offset refactor — a link in a prose
    # segment that follows BOTH a fence AND many (50) preceding lines must still
    # report the true 1-based line number (56 here), not drift.
    prefix = "\n".join("line %d" % i for i in range(1, 51))  # 50 lines, no trailer
    text = prefix + "\n\n```\ncode\n```\n\n[a](x.md)\n"
    got = lib.iter_markdown_links(text)
    assert any(t == "x.md" and ln == 56 for (_d, t, ln) in got)


def test_check_docs_oversized_file_is_warn_and_skipped(tmp_path, capsys):
    # M-DoS backstop: a file over _MAX_DOC_BYTES emits exactly ONE FILE_TOO_LARGE
    # warn (rc 0) and is NOT content-scanned — otherwise its 60k broken-link lines
    # would flood BROKEN_LINK errors (and hang the pre-refactor scanners).
    cli = _load_cli()
    big = "[gone](missing.md)\n" * 60000  # ~1.14 MB > 1_000_000
    _seed(tmp_path, "docs/big.md", big)
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0
    assert codes == ["FILE_TOO_LARGE"]  # one record; per-file content checks skipped


def test_redact_output_home_punctuation_and_case_boundary():
    # L-redact-home: home before punctuation (") and a case-mismatched home
    # (case-insensitive FS) both redact; a home followed by a word char
    # (/home/jackson) is left alone.
    src = 'path="/home/jack" and /HOME/JACK: end; /home/jackson stays\n'
    out = lib.redact_output(src, "/home/jack", "", "", [])
    assert 'path="~"' in out  # punctuation boundary (before the closing quote)
    assert "~: end" in out  # case-insensitive match + punctuation boundary (before :)
    assert "/home/jackson stays" in out  # word-char boundary preserved
    assert "/home/jack" not in out.replace("/home/jackson", "")  # both forms redacted


# ---- review session 3: identity match, link OSError, whitespace page ----


def test_check_docs_empty_tier_case_variant_page(tmp_path, capsys):
    # S3: a coverage `page` whose casing differs from disk. On a case-INSENSITIVE FS
    # (macOS/Windows) it names the SAME real file -> covered (samefile identity, not a
    # resolve()-string membership that preserves case and would false-positive
    # EMPTY_TIER). On a case-SENSITIVE FS the variant is a genuinely different, missing
    # path -> EMPTY_TIER is correct. Assert per FS.
    cli = _load_cli()
    page = _seed(tmp_path, "docs/manual/usage.md", "# Usage\n\nreal content\n")
    case_insensitive = (page.parent / "USAGE.MD").exists()
    cov = _seed(
        tmp_path,
        "docs/.onboard-coverage.json",
        '[{"surface":"Usage","slug":"usage","tier":"principal",'
        '"page":"docs/manual/Usage.md","status":"covered"}]',
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--coverage", str(cov)])
    if case_insensitive:
        assert rc == 0 and "EMPTY_TIER" not in codes  # samefile matches the case variant
    else:
        assert rc == 1 and "EMPTY_TIER" in codes  # genuinely different, missing path


def test_check_docs_pathological_link_target_does_not_abort(tmp_path, capsys):
    # S3: a link target with a component over NAME_MAX must not crash the gate to
    # exit 2 (the ENAMETOOLONG class hardened for coverage pages in S2-H2 but missed
    # in _check_links). It degrades to a finding and other files' findings survive.
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n[bad](%s.md)\n" % ("z" * 300))
    _seed(tmp_path, "docs/b.md", "# B\n\n[gone](missing.md)\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 1  # b.md's in-roots BROKEN_LINK is an error, NOT a fatal exit 2
    assert codes.count("BROKEN_LINK") == 2  # pathological + real both reported


def test_check_docs_empty_tier_whitespace_only_page(tmp_path, capsys):
    # LOW: the "empty" leg of EMPTY_TIER's null/missing/empty contract — a real,
    # coverage-linked manual page with whitespace-only content still errors.
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/usage.md", "   \n\t\n")  # whitespace only
    cov = _seed(
        tmp_path,
        "docs/.onboard-coverage.json",
        '[{"surface":"Usage","slug":"usage","tier":"principal",'
        '"page":"docs/manual/usage.md","status":"covered"}]',
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--coverage", str(cov)])
    assert rc == 1 and "EMPTY_TIER" in codes


# ---- follow-up: pre-existing v2 helper hardening ---------------------------


def test_rewrite_markdown_links_no_chaining_across_moves():
    # a move whose NEW equals another move's OLD must NOT chain: a.md -> b.md (its own
    # target), never a.md -> c.md. One simultaneous pass, no rule feeds another.
    out = lib.rewrite_markdown_links("[x](a.md) [y](b.md)\n", {"a.md": "b.md", "b.md": "c.md"})
    assert "[x](b.md)" in out and "[y](c.md)" in out
    assert "[x](c.md)" not in out
    # ref-def form is simultaneous too
    out2 = lib.rewrite_markdown_links("[x]: a.md\n[y]: b.md\n", {"a.md": "b.md", "b.md": "c.md"})
    assert "[x]: b.md" in out2 and "[y]: c.md" in out2


def test_renumber_toc_bom_prefixed_first_item():
    # a BOM (U+FEFF) immediately before the first ordered-list item must not offset
    # numbering; the BOM is preserved on the first line.
    out = lib.renumber_toc("﻿3. a\n1. b\n5. c\n")
    assert out == "﻿1. a\n2. b\n3. c\n"
    # BOM-only no-op path still preserves the BOM
    assert lib.renumber_toc("﻿no list here\n") == "﻿no list here\n"


# ---- update-deps: classify_artifact deps kind ----------------------------


def test_classify_deps_kind_by_content():
    assert (
        lib.classify_artifact(
            "Tier-based dependency update: cargo update --precise, "
            "npm install pkg@ver, verify_fast gates."
        )
        == "deps"
    )
    assert (
        lib.classify_artifact(
            "Update Directory.Packages.props and dotnet restore; "
            "bundledNativeModules via expo install --fix."
        )
        == "deps"
    )


def test_classify_deps_wins_over_incidental_docs_mention():
    # a deps command that mentions 'readme' classifies as deps, not docs
    assert (
        lib.classify_artifact(
            "Dependency update command; cargo update --precise per tier. See readme for notes."
        )
        == "deps"
    )


def test_classify_existing_kinds_unchanged_by_deps_addition():
    assert (
        lib.classify_artifact("Update CHANGELOG.md per Keep a Changelog and SemVer") == "changelog"
    )
    assert lib.classify_artifact("Audit README and docs/ for documentation drift") == "docs"
    assert lib.classify_artifact("Generate API reference from OpenAPI") is None


# ---- update-deps: find_predecessors self-exclusion fix -------------------


def _deps_body():
    return (
        "Tier-based dependency update. cargo update --precise for rust, "
        "npm install pkg@ver for js, verify_fast gates per tier."
    )


def test_find_predecessors_detects_legacy_update_deps_command(tmp_path):
    # 'update-deps' is now canonical, but a LEGACY commands/update-deps.md must
    # still surface for retirement (the self-exclusion bug the fix targets).
    claude = tmp_path / ".claude"
    _seed(claude, "commands/update-deps.md", _deps_body())
    found = lib.find_predecessors(claude)
    assert {f["name"]: f["kind"] for f in found} == {"update-deps": "deps"}
    assert all("commands" in f["path"] for f in found)


def test_find_predecessors_excludes_canonical_update_deps_skill(tmp_path):
    # the stamped skills/update-deps/SKILL.md is NOT a predecessor of itself.
    claude = tmp_path / ".claude"
    _seed(claude, "skills/update-deps/SKILL.md", _deps_body())
    assert lib.find_predecessors(claude) == []


def test_find_predecessors_namespaced_update_deps_command_detected(tmp_path):
    claude = tmp_path / ".claude"
    _seed(claude, "commands/release/update-deps.md", _deps_body())
    found = lib.find_predecessors(claude)
    assert [f["name"] for f in found] == ["update-deps"]
    assert found[0]["kind"] == "deps"


# ---- update-deps: stdlib detection helpers --------------------------------


def test_cargo_workspace_members():
    toml = (
        "[workspace]\n"
        'members = ["crates/core", "crates/cli"]\n'
        "[workspace.dependencies]\n"
        'serde = "1"\n'
    )
    assert lib.cargo_workspace_members(toml) == ["crates/core", "crates/cli"]
    assert lib.cargo_workspace_members("[package]\nname = 'x'\n") == []


def test_cargo_dep_kinds_classifies_pins():
    toml = (
        "[dependencies]\n"
        'serde = "1"\n'  # registry (caret)
        'libc = "=0.2"\n'  # exact
        'opus = { git = "https://example/o", rev = "abc" }\n'  # git
        'local = { path = "../local" }\n'  # path
    )
    kinds = lib.cargo_dep_kinds(toml)
    assert kinds["serde"] == "registry"
    assert kinds["libc"] == "exact"
    assert kinds["opus"] == "git"
    assert kinds["local"] == "path"


def test_cargo_dep_kinds_ignores_package_metadata():
    # section-scoped: [package] fields (name/version/authors/license/...) must
    # never be classified as dependencies. Locks the final-review fix.
    toml = (
        "[package]\n"
        'name = "mycrate"\n'
        'version = "0.1.0"\n'
        'authors = ["a@b.c"]\n'
        'license = "MIT"\n'
        'description = "a crate"\n'
        "[dependencies]\n"
        'serde = "1"\n'
    )
    assert lib.cargo_dep_kinds(toml) == {"serde": "registry"}


def test_package_json_deps_merges_dep_sets():
    pkg = '{"dependencies": {"ky": "^2.0.0"}, "devDependencies": {"jest": "^29.0.0"}}'
    deps = lib.package_json_deps(pkg)
    assert deps == {"ky": "^2.0.0", "jest": "^29.0.0"}


def test_package_resolved_pins_exposes_branch_revision():
    resolved = json.dumps(
        {
            "version": 3,
            "pins": [
                {
                    "identity": "swift",
                    "kind": "remoteSourceControl",
                    "location": "https://x",
                    "state": {"version": "1.2.0"},
                },
                {
                    "identity": "fork",
                    "kind": "remoteSourceControl",
                    "location": "https://y",
                    "state": {"branch": "dev", "revision": "deadbeef"},
                },
            ],
        }
    )
    pins = lib.package_resolved_pins(resolved)
    by_name = {p["name"]: p for p in pins}
    assert by_name["swift"]["version"] == "1.2.0" and by_name["swift"]["branch"] is None
    assert by_name["fork"]["branch"] == "dev" and by_name["fork"]["revision"] == "deadbeef"


def test_directory_packages_props_versions():
    props = (
        "<Project>\n"
        "  <ItemGroup>\n"
        '    <PackageVersion Include="Serilog" Version="4.0.0" />\n'
        '    <PackageVersion Include="Polly" Version="8.1.0" />\n'
        "  </ItemGroup>\n"
        "</Project>"
    )
    assert lib.directory_packages_props_versions(props) == {"Serilog": "4.0.0", "Polly": "8.1.0"}


# ---- update-deps: deps-detect verb ---------------------------------------


def test_deps_detect_emits_json_for_a_polyglot_tree(tmp_path, capsys):
    cli = _load_cli()
    # js root + a rust workspace root
    _seed(tmp_path, "package.json", '{"dependencies": {"ky": "^2.0.0"}}')
    _seed(
        tmp_path,
        "rust/Cargo.toml",
        '[workspace]\nmembers = ["crates/a"]\n[workspace.dependencies]\nserde = "1"\n',
    )
    rc = cli.main(["deps-detect", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    names = {e["name"] for e in out["ecosystems"]}
    assert names == {"js", "rust"}
    rust = next(e for e in out["ecosystems"] if e["name"] == "rust")
    assert rust["manager"] == "cargo"
    assert rust["workspaces"] and rust["workspaces"][0]["root"].endswith("rust")


def test_deps_detect_exits_2_when_no_supported_ecosystem(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "README.md", "# nothing here")
    rc = cli.main(["deps-detect", str(tmp_path)])
    assert rc == 2
    assert "Traceback" not in capsys.readouterr().err


# ---- update-deps: template invariants ------------------------------------

UPD_DEPS = ONBOARD / "templates" / "update-deps" / "SKILL.md"


def test_update_deps_template_exists_with_one_repo_specifics_block():
    assert UPD_DEPS.is_file(), "templates/update-deps/SKILL.md must exist"
    raw = UPD_DEPS.read_text(encoding="utf-8")
    lib.parse_regions(raw)  # exactly one well-formed BEGIN/END block


def test_update_deps_template_is_deliberate_only_with_flags():
    raw = UPD_DEPS.read_text(encoding="utf-8")
    fm = raw.split("---", 2)[1]
    assert "disable-model-invocation: true" in fm  # destructive -> deliberate-only
    assert "argument-hint" in fm  # --dry-run / --ecosystem / --tier
    assert "--dry-run" in fm


def test_update_deps_template_provenance_matches_template_version():
    raw = UPD_DEPS.read_text(encoding="utf-8")
    assert "stamped by onboard-repo v%s " % lib.TEMPLATE_VERSION in raw


def test_update_deps_template_pins_core_rules():
    t = _norm(UPD_DEPS)
    # universal pipeline + tiers + safety
    assert "baseline" in t and "tier" in t
    assert "patch" in t and "minor" in t and "major" in t
    assert "skip" in t
    assert "verifyfast" in t and "verifyfull" in t
    # the four adapters
    for eco in ("npm", "cargo", "--precise", "swift", "dotnet", "directory.packages.props"):
        assert eco in t, eco
    # carry-over safety rules
    assert "--precise" in t
    assert "bundlednativemodules" in t or "expo install --fix" in t
    assert "resolve tier" in t  # SPM carve-out
    # never bulk / never @latest
    assert "never" in t and "specific" in t


# ---- Task 6: SKILL.md documents update-deps opt-in + deps-detect ------------


def test_skill_documents_update_deps_opt_in_and_deps_detect():
    t = SKILL.read_text(encoding="utf-8").lower()
    assert "update-deps" in t
    assert "--with update-deps" in t or "opt-in" in t
    assert "deps-detect" in t  # the detection verb
    # predecessor retirement of a legacy /update-deps command via the deps kind
    assert "commands/update-deps.md" in t or "retire" in t


# ---- Task 7: references cover update-deps detection + stamping -------------


def test_references_cover_update_deps_detection_and_stamping():
    det = DETECT.read_text(encoding="utf-8").lower()
    assert "deps-detect" in det
    assert "ecosystem" in det and "workspace" in det
    stamping = (ONBOARD / "references" / "stamping.md").read_text(encoding="utf-8").lower()
    assert "update-deps" in stamping
    assert "verify_fast" in stamping and "verify_full" in stamping


# ---- Task 8: project agent configuration (settings.json + .gitignore) ------


def _buckets(names):
    return lib.plan_project_permissions(names)["permissions"]


def test_allow_drops_builtin_readonly_bash_but_keeps_powershell():
    # Claude Code already runs read-only git unprompted via a built-in set, so a
    # Bash allow entry is dead weight -- but PowerShell has no such carve-out.
    out = lib.pair_shell_rules(
        ["Bash(git log:*)", "Bash(grep:*)", "Bash(dotnet build:*)"], drop_builtin_bash=True
    )
    assert "Bash(git log:*)" not in out
    assert "Bash(grep:*)" not in out
    assert "PowerShell(git log:*)" in out
    assert "PowerShell(grep:*)" in out
    # a mutating command survives in both forms
    assert "Bash(dotnet build:*)" in out and "PowerShell(dotnet build:*)" in out


def test_ask_and_deny_keep_both_shell_forms():
    # Permission rules match per tool: Bash(git reset:*) does NOT block
    # PowerShell(git reset ...). Dropping either form leaves a hole in the guard.
    out = lib.pair_shell_rules(["Bash(git log:*)"])
    assert out == ["Bash(git log:*)", "PowerShell(git log:*)"]


@pytest.mark.parametrize("bucket", ["ask", "deny"])
def test_every_shell_rule_is_paired_in_ask_and_deny(bucket):
    rules = _buckets(["dotnet"])[bucket]
    shell = [r for r in rules if r.startswith(("Bash(", "PowerShell("))]
    bodies_bash = {r[len("Bash(") : -1] for r in shell if r.startswith("Bash(")}
    bodies_ps = {r[len("PowerShell(") : -1] for r in shell if r.startswith("PowerShell(")}
    assert bodies_bash == bodies_ps, "unpaired shell rule leaves a per-tool hole"


def test_allow_never_contains_a_builtin_readonly_bash_entry():
    for rule in _buckets(["dotnet", "js", "rust", "swift"])["allow"]:
        if rule.startswith("Bash("):
            assert not lib._is_builtin_readonly_bash(rule[len("Bash(") : -1])


def test_plan_asks_before_credential_shaped_paths_for_read_and_edit():
    perms = _buckets(["dotnet"])
    for glob in ("**/.env*", "**/appsettings*.json"):
        assert "Read(%s)" % glob in perms["ask"]
        assert "Edit(%s)" % glob in perms["ask"]
    # `**/.ssh/**` is deliberately gone: a relative glob anchors under the project, so
    # it only ever matched a `.ssh` INSIDE the repo. The real one is the user's own
    # `~/.ssh/**` rule, which a shared project file has no business restating.
    assert not any(".ssh" in r or ".aws" in r for r in perms["ask"] + perms["deny"])
    # deny keeps the shell guards only -- no path rule may sit there, or a shared
    # project file would convert the user's global "ask me" into "never".
    assert all(r.startswith(("Bash(", "PowerShell(")) for r in perms["deny"])


def test_plan_degrades_to_baseline_on_unknown_or_empty_ecosystem():
    # A newly supported ecosystem must not break onboarding, and a repo with no
    # detected ecosystem still deserves the git and credential guards.
    for names in ([], None, ["haskell"]):
        p = lib.plan_project_permissions(names)["permissions"]
        assert "Bash(git fetch:*)" in p["allow"]
        assert "Bash(git reset:*)" in p["deny"]
        assert not any("dotnet" in r for r in p["allow"])


def test_plan_is_deterministic_and_dedupes():
    a = lib.plan_project_permissions(["dotnet", "dotnet"])
    b = lib.plan_project_permissions(["dotnet"])
    assert a == b
    allow = a["permissions"]["allow"]
    assert len(allow) == len(set(allow))


def test_ensure_gitignore_lines_is_idempotent():
    first = lib.ensure_gitignore_lines("node_modules\n", [".claude/settings.local.json"])
    assert first.endswith(".claude/settings.local.json\n")
    assert lib.ensure_gitignore_lines(first, [".claude/settings.local.json"]) == first
    # unchanged input returns the identical object-value so the caller can skip the write
    assert lib.ensure_gitignore_lines("a\n", ["a"]) == "a\n"


def test_ensure_gitignore_lines_handles_missing_trailing_newline_and_empty():
    assert lib.ensure_gitignore_lines("x", ["y"]) == "x\ny\n"
    assert lib.ensure_gitignore_lines("", ["y"]) == "y\n"
    assert lib.ensure_gitignore_lines(None, ["y"]) == "y\n"


def test_cli_settings_plan_and_gitignore_ensure(tmp_path, capsys):
    cli = _load_cli()
    assert cli.main(["settings-plan", str(tmp_path), "--ecosystem", "dotnet"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert "Bash(dotnet build:*)" in plan["permissions"]["allow"]

    gi = tmp_path / ".gitignore"
    gi.write_text("node_modules\n", encoding="utf-8")
    assert cli.main(["gitignore-ensure", str(gi), ".claude/settings.local.json"]) == 0
    assert ".claude/settings.local.json" in capsys.readouterr().out


def test_cli_settings_plan_rejects_bad_input(tmp_path, capsys):
    cli = _load_cli()
    assert cli.main(["settings-plan", str(tmp_path / "nope")]) == 2
    assert cli.main(["settings-plan", str(tmp_path), "--bogus"]) == 2
    assert cli.main(["gitignore-ensure"]) == 2


def test_cli_gitignore_ensure_treats_missing_file_as_empty(tmp_path, capsys):
    cli = _load_cli()
    missing = tmp_path / ".gitignore"
    assert cli.main(["gitignore-ensure", str(missing), "a"]) == 0
    assert capsys.readouterr().out == "a\n"


# ---- Task 9: an onboarded permission plan is audited and migrated (ADR-0017) ----
#
# Claude Code 2.1.259 treated a path-less `rg` / `grep -r` / `git` / `cp` / `mv` as a
# read of the directory it scans and checked that directory against every `Read()`
# deny rule's static prefix. A rule anchored INSIDE the repo -- `**/x`, `x`, `./x`,
# `/x` -- has its prefix in the working directory, so every such command became a
# human-only prompt. The pre-ADR-0009 planner emitted exactly those rules, and
# nothing ever re-visited an onboarded repo's `.claude/settings.json`. 2.1.260
# reverted the directory check; `//**/` still covers strictly more, so the migration
# and these tests stand.

_LEGACY_PLAN = {
    "permissions": {
        "allow": [
            "Bash(npm test:*)",
            "Bash(npx*)",
            "Bash(curl * http://localhost:*)",
            "Bash(xargs:*)",
        ],
        "ask": ["Read(**/.env*)", "Edit(**/.env*)"],
        "deny": [
            "Bash(git reset:*)",
            "PowerShell(git reset:*)",
            "Read(**/.env)",
            "Edit(**/.env)",
            "Read(**/.ssh/**)",
            "Edit(**/.ssh/**)",
            "Read(.keystore/**)",
            "Read(certs/**)",
            "Read(./secrets.json)",
            "Read(/config/prod.yml)",
            "Edit(registry.json)",
            "Read(//**/*.pem)",
            "Read(~/.aws/**)",
        ],
    },
    "other": {"kept": True},
}


def test_audit_names_every_deny_read_rule_anchored_inside_the_repo():
    a = lib.audit_project_permissions(_LEGACY_PLAN)
    # `//`- and `~`-anchored rules never trigger; an Edit-only rule does not gate a
    # read; `ask` is not consulted by the directory-read guard at all.
    assert a["guard_triggers"] == [
        "Read(**/.env)",
        "Read(**/.ssh/**)",
        "Read(.keystore/**)",
        "Read(certs/**)",
        "Read(./secrets.json)",
        "Read(/config/prod.yml)",
    ]


def test_audit_flags_home_directory_denies_as_dead_in_project_scope():
    # A relative glob anchors under the project, so `**/.ssh/**` only ever matched a
    # `.ssh` directory INSIDE the repo -- pure trigger, zero coverage.
    a = lib.audit_project_permissions(_LEGACY_PLAN)
    assert a["dead_home_denies"] == ["Read(**/.ssh/**)", "Edit(**/.ssh/**)"]


def test_audit_flags_broad_allows_with_the_payload_rules():
    # The same three shapes test_payload.py refuses in the shipped payload: a
    # wildcarded interpreter, an argument-pinned fetcher, a command wrapper.
    a = lib.audit_project_permissions(_LEGACY_PLAN)
    assert a["broad_allows"] == ["Bash(npx*)", "Bash(curl * http://localhost:*)", "Bash(xargs:*)"]


def test_audit_tolerates_a_file_with_no_permissions():
    assert lib.audit_project_permissions({}) == {
        "guard_triggers": [],
        "dead_home_denies": [],
        "broad_allows": [],
    }


@pytest.mark.parametrize("names", [[], ["js"], ["dotnet", "python"], ["php", "rust", "swift"]])
def test_audit_is_clean_on_everything_the_planner_emits(names):
    a = lib.audit_project_permissions(lib.plan_project_permissions(names))
    assert a == {"guard_triggers": [], "dead_home_denies": [], "broad_allows": []}


def test_migrate_reanchors_every_inside_repo_deny_at_the_filesystem_root():
    # `//**/<path>` matches the same files under this repo AND everywhere else -- a
    # strict superset, so nothing is less protected -- and its static prefix is `/`,
    # which is inside no working directory, so the guard never fires on it.
    new, actions = lib.migrate_project_permissions(_LEGACY_PLAN)
    deny = new["permissions"]["deny"]
    for old, expected in [
        ("Read(**/.env)", "Read(//**/.env)"),
        ("Edit(**/.env)", "Edit(//**/.env)"),
        ("Read(**/.ssh/**)", "Read(//**/.ssh/**)"),
        ("Read(.keystore/**)", "Read(//**/.keystore/**)"),
        ("Read(certs/**)", "Read(//**/certs/**)"),
        ("Read(./secrets.json)", "Read(//**/secrets.json)"),
        ("Read(/config/prod.yml)", "Read(//**/config/prod.yml)"),
        ("Edit(registry.json)", "Edit(//**/registry.json)"),
    ]:
        assert expected in deny and old not in deny
        assert {"tier": "deny", "from": old, "to": expected} in actions
    # untouched: shell rules, already-anchored rules, the ask and allow tiers, other keys
    assert "Bash(git reset:*)" in deny and "Read(//**/*.pem)" in deny and "Read(~/.aws/**)" in deny
    assert new["permissions"]["ask"] == _LEGACY_PLAN["permissions"]["ask"]
    assert new["permissions"]["allow"] == _LEGACY_PLAN["permissions"]["allow"]
    assert new["other"] == {"kept": True}
    assert lib.audit_project_permissions(new)["guard_triggers"] == []


def test_migrate_keeps_order_dedupes_against_an_existing_twin_and_is_idempotent():
    s = {"permissions": {"deny": ["Read(**/*.pem)", "Read(//**/*.pem)", "Bash(git reset:*)"]}}
    new, actions = lib.migrate_project_permissions(s)
    assert new["permissions"]["deny"] == ["Read(//**/*.pem)", "Bash(git reset:*)"]
    assert actions == [{"tier": "deny", "from": "Read(**/*.pem)", "to": "Read(//**/*.pem)"}]
    again, more = lib.migrate_project_permissions(new)
    assert again == new and more == []


def test_migrate_never_mutates_its_input_and_tolerates_missing_permissions():
    import copy as _copy

    snapshot = _copy.deepcopy(_LEGACY_PLAN)
    lib.migrate_project_permissions(_LEGACY_PLAN)
    assert _LEGACY_PLAN == snapshot
    assert lib.migrate_project_permissions({}) == ({}, [])


def _legacy_repo(tmp_path):
    f = tmp_path / ".claude" / "settings.json"
    f.parent.mkdir()
    f.write_text(json.dumps(_LEGACY_PLAN, indent=2) + "\n", encoding="utf-8")
    return f


def test_cli_settings_audit_reports_and_exits_one_on_a_guard_trigger(tmp_path, capsys):
    cli = _load_cli()
    f = _legacy_repo(tmp_path)
    assert cli.main(["settings-audit", str(f)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert "Read(**/.env)" in out["guard_triggers"]
    assert "Bash(xargs:*)" in out["broad_allows"]
    assert f.read_text(encoding="utf-8").endswith("\n")  # never written


def test_cli_settings_audit_exits_zero_on_a_clean_plan(tmp_path, capsys):
    cli = _load_cli()
    f = tmp_path / "settings.json"
    f.write_text(json.dumps(lib.plan_project_permissions(["js"])), encoding="utf-8")
    assert cli.main(["settings-audit", str(f)]) == 0
    assert json.loads(capsys.readouterr().out)["guard_triggers"] == []


def test_cli_settings_migrate_is_a_dry_run_by_default(tmp_path, capsys):
    cli = _load_cli()
    f = _legacy_repo(tmp_path)
    before = f.read_text(encoding="utf-8")
    assert cli.main(["settings-migrate", str(f)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert {"tier": "deny", "from": "Read(**/.env)", "to": "Read(//**/.env)"} in out["actions"]
    assert out["written"] is False
    assert f.read_text(encoding="utf-8") == before
    assert not (tmp_path / ".onboard-repo-retired").exists()


def test_cli_settings_migrate_apply_writes_and_backs_up_under_the_retire_dir(tmp_path, capsys):
    cli = _load_cli()
    f = _legacy_repo(tmp_path)
    assert cli.main(["settings-migrate", str(f), "--apply", "--stamp", "20260904T000000"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["written"] is True
    new = json.loads(f.read_text(encoding="utf-8"))
    assert "Read(//**/.env)" in new["permissions"]["deny"]
    assert "Read(**/.env)" not in new["permissions"]["deny"]
    assert new["other"] == {"kept": True}
    backup = tmp_path / ".onboard-repo-retired" / "20260904T000000" / "settings.json"
    assert json.loads(backup.read_text(encoding="utf-8")) == _LEGACY_PLAN
    assert lib.audit_project_permissions(new)["guard_triggers"] == []


def test_cli_settings_migrate_apply_with_nothing_to_do_writes_nothing(tmp_path, capsys):
    cli = _load_cli()
    f = tmp_path / ".claude" / "settings.json"
    f.parent.mkdir()
    f.write_text(json.dumps(lib.plan_project_permissions(["js"])) + "\n", encoding="utf-8")
    before = f.read_text(encoding="utf-8")
    assert cli.main(["settings-migrate", str(f), "--apply", "--stamp", "20260904T000000"]) == 0
    assert json.loads(capsys.readouterr().out) == {"actions": [], "written": False}
    assert f.read_text(encoding="utf-8") == before
    assert not (tmp_path / ".onboard-repo-retired").exists()


def test_cli_settings_migrate_rejects_bad_input(tmp_path, capsys):
    cli = _load_cli()
    f = _legacy_repo(tmp_path)
    # --apply without a stamp would silently pick a time; that is a usage error here
    assert cli.main(["settings-migrate", str(f), "--apply"]) == 2
    assert cli.main(["settings-migrate", str(f), "--bogus"]) == 2
    assert cli.main(["settings-migrate", str(tmp_path / "nope.json")]) == 2
    assert cli.main(["settings-audit"]) == 2
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    assert cli.main(["settings-audit", str(tmp_path / "broken.json")]) == 2


def test_skill_audits_on_check_and_offers_the_migration_on_sync():
    t = SKILL.read_text(encoding="utf-8")
    assert "settings-audit" in t and "settings-migrate" in t


def test_skill_provisions_agent_config_without_a_git_grant():
    t = SKILL.read_text(encoding="utf-8")
    assert "settings-plan" in t and "gitignore-ensure" in t
    assert ".claude/settings.local.json" in t
    # untracking is operator-run: onboard-repo carries no git-mutation grant
    assert "git rm --cached" in t
    fm = t.split("---", 2)[1]
    assert "git rm" not in fm


def test_skill_never_writes_over_an_existing_settings_file():
    t = SKILL.read_text(encoding="utf-8").lower()
    assert "never `write` over it" in t or "never write over it" in t
    assert "merge additively" in t


def test_skill_scaffolds_rules_dir_but_never_authors_rules():
    t = SKILL.read_text(encoding="utf-8").lower()
    assert ".claude/rules/" in t
    assert "do not author repo-specific rules" in t


def test_agent_instructions_template_records_the_decision_rule():
    p = ONBOARD / "templates" / "docs-ia" / "internals-agent-instructions.md"
    t = p.read_text(encoding="utf-8").lower()
    assert "load timing" in t  # the actual rule/skill distinction
    assert "read, never on write" in t or "fires on read" in t  # the paths trap
    assert "per tool" in t  # why ask/deny needs both shell forms
    assert "built-in set of read-only bash commands" in t
    assert "one fact, one home" in t


def test_agents_template_indexes_rules_and_skills():
    t = (ONBOARD / "templates" / "docs-ia" / "AGENTS.md").read_text(encoding="utf-8")
    assert ".claude/rules/" in t and ".claude/skills/" in t
    assert "agent-instructions.md" in t
    assert "stale pointer" in t.lower()


def test_skill_copies_the_agent_instructions_template():
    t = SKILL.read_text(encoding="utf-8")
    assert "internals-agent-instructions.md" in t
    assert "docs/internals/agent-instructions.md" in t


def test_rules_example_template_is_inert_until_filled_in():
    p = ONBOARD / "templates" / "docs-ia" / "rules-EXAMPLE.md"
    body = p.read_text(encoding="utf-8")
    # It must carry paths: frontmatter -- an unscoped rule taxes every session.
    assert body.startswith("---\n")
    fm = body.split("---", 2)[1]
    assert "paths:" in fm
    # The placeholder glob is angle-bracketed, so it matches no real file and the
    # scaffolded example costs no context until the operator fills it in.
    assert "<" in fm and ">" in fm
    low = body.lower()
    assert "delete this file" in low  # it is scaffolding, not a keeper
    for test in ("declarative", "expensive to violate", "re-derivable"):
        assert test in low
    assert "read, never on write" in low or "fires on read" in low


def test_skill_scaffolds_the_example_rule_and_cites_the_adr():
    t = SKILL.read_text(encoding="utf-8")
    assert "rules-EXAMPLE.md" in t
    assert "ADR-0002" in t


# ---- Task 9: grounding the claims in rules and skills ---------------------


def _always(_p, _n):
    return True


def _never(_p, _n):
    return False


def test_citations_are_extracted_from_prose_but_not_from_fences():
    text = (
        "See `Domain/Models/Result.cs:7` for the struct.\n"
        "```csharp\n"
        "// Infrastructure/Repositories/PersonRepository.cs:26\n"
        "```\n"
        "And `AGENTS.md:21`.\n"
    )
    got = [(p, n) for _ln, p, n in lib.iter_citations(text)]
    # a path inside a fence is illustrative, not a citation
    assert got == [("Domain/Models/Result.cs", 7), ("AGENTS.md", 21)]


def test_citation_extractor_ignores_globs_urls_and_permission_rules():
    text = (
        "Rule `Bash(git log:*)` and glob `**/*.cs` and url https://example.com:443 "
        "and `Read(**/*.env)`.\n"
    )
    assert list(lib.iter_citations(text)) == []


def test_citation_accepts_a_line_range_by_its_first_line():
    text = "See `a/b/Thing.cs:26-34`.\n"
    assert [(p, n) for _ln, p, n in lib.iter_citations(text)] == [("a/b/Thing.cs", 26)]


def test_unresolved_citation_is_an_error_and_resolved_is_silent():
    text = "See `Domain/Models/Result.cs:7`.\n"
    assert lib.check_instructions(text, _always) == []
    findings = lib.check_instructions(text, _never)
    assert [(f[0], f[1]) for f in findings] == [("error", "UNRESOLVED_CITATION")]


def test_count_claims_need_a_re_derivation_command_nearby():
    ungrounded = "This convention covers 446 files today.\n"
    assert [f[1] for f in lib.check_instructions(ungrounded, _always)] == ["UNGROUNDED_COUNT"]
    grounded = "This convention covers 446 files today.\n\n    rg -l 'X' | wc -l\n"
    assert lib.check_instructions(grounded, _always) == []


def test_count_claim_grounding_window_is_bounded():
    # the command must be NEAR the claim; six lines away is not grounding
    far = "covers 446 files\n" + "\n" * 6 + "rg -l 'X'\n"
    assert [f[1] for f in lib.check_instructions(far, _always)] == ["UNGROUNDED_COUNT"]


def test_bare_numbers_without_a_countable_noun_are_not_claims():
    # "3 rounds" / "two tiers" are prose, not assertions about the codebase
    for text in ("Stop after 3 rounds.\n", "It uses 2 tiers.\n", "Version 0.2.17.\n"):
        assert lib.check_instructions(text, _always) == []


def test_count_claims_are_not_extracted_from_fences():
    assert lib.check_instructions("```\n446 files\n```\n", _always) == []


def test_cli_check_instructions_resolves_shorthand_and_flags_real_misses(tmp_path):
    cli = _load_cli()
    src = tmp_path / "deep" / "nested"
    src.mkdir(parents=True)
    (src / "Thing.cs").write_text("\n" * 50, encoding="utf-8")
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)

    # bare filename and partial path both resolve by path-suffix
    (rules / "ok.md").write_text("See `Thing.cs:10` and `nested/Thing.cs:20`.\n", encoding="utf-8")
    assert cli.main(["check-instructions", str(rules), "--repo-root", str(tmp_path)]) == 0

    # a path naming no file, and a line past the end of a real file, still error
    (rules / "bad.md").write_text(
        "See `no/such/File.cs:1` and `Thing.cs:9999`.\n", encoding="utf-8"
    )
    assert cli.main(["check-instructions", str(rules), "--repo-root", str(tmp_path)]) == 1


def test_cli_check_instructions_accepts_repeated_repo_root(tmp_path, capsys):
    cli = _load_cli()
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "Only.cs").write_text("\n" * 5, encoding="utf-8")
    doc = tmp_path / "r.md"
    doc.write_text("See `Only.cs:3`.\n", encoding="utf-8")
    # resolvable under the second base only
    assert (
        cli.main(
            [
                "check-instructions",
                str(doc),
                "--repo-root",
                str(tmp_path / "a"),
                "--repo-root",
                str(tmp_path / "b"),
            ]
        )
        == 0
    )


def test_cli_check_instructions_rejects_bad_input(tmp_path):
    cli = _load_cli()
    assert cli.main(["check-instructions"]) == 2
    assert cli.main(["check-instructions", str(tmp_path / "nope")]) == 2
    assert cli.main(["check-instructions", str(tmp_path), "--repo-root", "/nope"]) == 2


def test_skill_wires_check_instructions_into_check_mode():
    t = SKILL.read_text(encoding="utf-8")
    assert "check-instructions" in t
    low = " ".join(t.lower().split())
    # warnings must be described as advisory, or the gate becomes unusable
    assert "ungrounded_count" in low or "warning" in low


def test_skill_grounds_existing_instruction_files_on_the_default_path():
    # It must run on a normal onboarding, not only under --check: a repo arriving
    # with its own rules is exactly where stale claims hide.
    t = SKILL.read_text(encoding="utf-8")
    before_check_mode = t.split("## 6.")[0]
    assert "check-instructions" in before_check_mode
    low = " ".join(before_check_mode.lower().split())
    # ...but onboarding reports, it does not rewrite someone else's rules
    assert "do not fix them here" in low
    assert "skip it when" in low  # nothing to ground on a fresh scaffold


def test_skill_rule_mining_is_validated_or_unavailable():
    t = SKILL.read_text(encoding="utf-8")
    assert "3.4c" in t and "ADR-0013" in t
    low = " ".join(t.lower().split())
    # three passes: mechanical + two independent, differently-briefed verifiers
    assert "truth verifier" in low and "worth verifier" in low
    assert "both verifiers must pass" in low
    # validation is inseparable -- --no-review loses the pass, not the verifiers
    assert "disables this pass entirely" in low
    # an unverified rule never reaches disk
    assert "never to disk" in low
    # offer-first, like every other mining pass
    assert "never run it unasked" in low


# --- grounding: does the instruction file actually LOAD, and can it FIRE? -------
# Motivated by a real migration where 17 of 21 rules carried YAML-invalid
# frontmatter. The existing citation/count checks passed them clean, because a rule
# that fails to parse has no bad citations -- it has nothing at all.


def _rule(fm, body="\n# R\n"):
    return "---\n" + fm + "\n---\n" + body


def _codes(findings):
    return sorted({c for _, c, _, _ in findings})


def test_unquoted_colon_in_frontmatter_is_an_error():
    # The exact shape that broke 17 rules: YAML reads `description:` as a nested
    # mapping and rejects the document, so the rule silently never loads.
    broken = _rule('paths:\n  - "src/**/*.ts"\ndescription: Observers: side-effect containers')
    findings = lib.check_instructions(broken, lambda p, n: True, kind="rule")
    assert _codes(findings) == ["INVALID_FRONTMATTER"]
    assert findings[0][0] == "error"


def test_quoting_the_value_clears_it():
    ok = _rule('paths:\n  - "src/**/*.ts"\ndescription: "Observers: side-effect containers"')
    assert lib.check_instructions(ok, lambda p, n: True, kind="rule") == []


@pytest.mark.parametrize(
    "fm",
    [
        'paths:\n  - "a.ts"\nfoo: bar',  # plain scalar, no colon
        'paths:\n  - "a.ts"\ndesc: |\n  block: scalar',  # block scalars may contain colons
        'paths:\n  - "a.ts"\ndesc: [one, two]',  # flow sequence
        'paths:\n  - "a.ts"\n# comment: with colon',  # comments are not mappings
    ],
)
def test_valid_frontmatter_shapes_are_not_flagged(fm):
    assert lib.check_instructions(_rule(fm), lambda p, n: True) == []


def test_unterminated_frontmatter_is_an_error():
    findings = lib.check_instructions("---\npaths:\n  - a\n", lambda p, n: True)
    assert _codes(findings) == ["INVALID_FRONTMATTER"]


def test_tab_in_frontmatter_is_an_error():
    findings = lib.check_instructions("---\npaths:\n\t- a.ts\n---\n", lambda p, n: True)
    assert "INVALID_FRONTMATTER" in _codes(findings)


def test_missing_paths_warns_on_a_rule_but_not_on_a_skill():
    text = _rule('description: "no scope"')
    rule = lib.check_instructions(text, lambda p, n: True, kind="rule")
    assert [(s, c) for s, c, _, _ in rule] == [("warn", "MISSING_PATHS")]
    # A skill without paths: is normal -- it loads on invocation, not on read.
    assert lib.check_instructions(text, lambda p, n: True, kind="skill") == []
    # Unknown kind must not guess.
    assert lib.check_instructions(text, lambda p, n: True) == []


def test_glob_matching_nothing_is_a_dead_rule():
    text = _rule('paths:\n  - "src/routing/**/*.ts"\ndescription: "d"')
    findings = lib.check_instructions(
        text, lambda p, n: True, kind="rule", glob_matches=lambda g: 0
    )
    assert [(s, c) for s, c, _, _ in findings] == [("error", "DEAD_GLOB")]
    # ...and a glob that matches is silent.
    assert (
        lib.check_instructions(text, lambda p, n: True, kind="rule", glob_matches=lambda g: 3) == []
    )


def test_placeholder_glob_is_not_a_dead_rule():
    # The scaffolded EXAMPLE ships an angle-bracketed glob on purpose so it stays
    # inert. It must not fail the gate it is meant to teach.
    text = _rule('paths:\n  - "<glob naming the file shape, e.g. **/*.ts>"\ndescription: "d"')
    assert (
        lib.check_instructions(text, lambda p, n: True, kind="rule", glob_matches=lambda g: 0) == []
    )


def test_flow_sequence_paths_are_read_too():
    text = _rule('paths: ["a/**/*.ts", "b/**/*.ts"]\ndescription: "d"')
    assert [g for _, g in lib.iter_path_globs(text)] == ["a/**/*.ts", "b/**/*.ts"]


def test_undefined_script_is_an_error_in_a_command_block():
    text = "Run it:\n\n```bash\nnpm run e2e\n```\n"
    findings = lib.check_instructions(text, lambda p, n: True, known_scripts={"test:e2e"})
    assert [(s, c) for s, c, _, _ in findings] == [("error", "UNDEFINED_SCRIPT")]
    assert lib.check_instructions(text, lambda p, n: True, known_scripts={"e2e"}) == []


def test_no_package_json_skips_the_script_check_rather_than_failing_everything():
    text = "```bash\nnpm run whatever\n```\n"
    assert lib.check_instructions(text, lambda p, n: True, known_scripts=None) == []


@pytest.mark.parametrize(
    "prose",
    [
        "`npm run e2e` was never defined in package.json.",
        "`npm run e2e` and `npm run e2e:ui` were cited 11x while only\n`test:e2e` existed.",
        "verify_fast is typically `npm run typecheck && npm test`.",
        "Ecosystem default: js `npm run typecheck`.",
    ],
)
def test_narration_about_a_missing_script_is_not_an_instruction(prose):
    # Documenting that a script does not exist is the point of the sentence. A gate
    # that fires loudest on the file explaining the problem gets switched off.
    assert lib.check_instructions(prose + "\n", lambda p, n: True, known_scripts={"test:e2e"}) == []


def test_narration_marker_is_found_across_a_wrapped_line():
    # Markdown wraps at 80 columns, so a two-word marker is routinely split. Matching
    # line-wise would miss it and report a false error.
    wrapped = "`npm run e2e` were cited 11x while `package.json` only\never defined `test:e2e`.\n"
    assert lib.check_instructions(wrapped, lambda p, n: True, known_scripts={"test:e2e"}) == []


def test_existing_citation_and_count_checks_are_unchanged():
    # The new arguments are optional; omitting them must reproduce the old behaviour.
    text = "See `nope.ts:9` for the 42 rules.\n"
    findings = lib.check_instructions(text, lambda p, n: False)
    assert _codes(findings) == ["UNGROUNDED_COUNT", "UNRESOLVED_CITATION"]


# --- migrating Copilot instruction files ---------------------------------------


def test_apply_to_becomes_a_paths_block():
    src = (
        '---\napplyTo: "src/hooks/**/*.ts,src/hooks/**/*.tsx"\n'
        'description: "Custom hook conventions: directory structure"\n---\n\n# Hooks\n'
    )
    new, notes = lib.convert_copilot_instruction(src)
    assert [g for _, g in lib.iter_path_globs(new)] == ["src/hooks/**/*.ts", "src/hooks/**/*.tsx"]
    assert "applyTo" not in new
    assert "# Hooks" in new  # body preserved
    assert any("2 globs" in n for n in notes)


def test_conversion_emits_frontmatter_that_passes_the_gate():
    # The migration that motivated this dropped the source's quotes and produced 17
    # rules YAML rejects. Converting must not be able to introduce that.
    src = '---\napplyTo: "**/*.ts"\ndescription: Observers: side-effect containers\n---\n\nbody\n'
    new, _ = lib.convert_copilot_instruction(src)
    assert lib.check_instructions(new, lambda p, n: True, kind="rule") == []


def test_non_copilot_files_are_left_alone():
    plain = '---\npaths:\n  - "a.ts"\n---\n\nbody\n'
    new, notes = lib.convert_copilot_instruction(plain)
    assert new == plain
    assert "not a Copilot instruction file" in notes[0]


def test_input_placeholders_become_named_arguments():
    src = "Create `src/hooks/use${input:HookName}/use${input:HookName}.ts`\n"
    new, args, _ = lib.convert_copilot_prompt(src)
    assert "${input:" not in new
    assert new.count("$HookName") == 2
    assert args == ["HookName"]  # de-duplicated, order preserved


def test_a_placeholder_glued_to_an_identifier_is_refused_not_guessed():
    # ${input:X} has delimiters; $X does not. Converting `${input:Name}Props` to
    # `$NameProps` silently renames the variable, so the converter declines.
    src = "export type ${input:ComponentName}Props = {};\n"
    new, args, notes = lib.convert_copilot_prompt(src)
    assert new == src  # untouched
    assert args == []
    assert any("different variable" in n for n in notes)


def test_a_placeholder_at_a_safe_boundary_still_converts():
    for boundary in ("/", ".", " ", ")", "`"):
        src = "x${input:Name}%s\n" % boundary
        new, args, _ = lib.convert_copilot_prompt(src)
        assert new == "x$Name%s\n" % boundary
        assert args == ["Name"]


def test_rules_example_teaches_the_quoting_trap():
    p = ONBOARD / "templates" / "docs-ia" / "rules-EXAMPLE.md"
    body = p.read_text(encoding="utf-8")
    fm = body.split("---", 2)[1]
    # The scaffold must model a quoted description, not just describe one.
    assert 'description: "' in fm
    low = " ".join(body.lower().split())
    assert "invalid_frontmatter" in low
    assert "does not load" in low or "simply absent" in low
    # ...and the example itself must pass the gate it teaches.
    findings = lib.check_instructions(
        body, lambda p_, n: True, kind="rule", glob_matches=lambda g: 0
    )
    assert findings == []


def test_skill_documents_the_load_time_codes_and_the_copilot_port():
    t = SKILL.read_text(encoding="utf-8")
    for code in ("INVALID_FRONTMATTER", "DEAD_GLOB", "UNDEFINED_SCRIPT", "MISSING_PATHS"):
        assert code in t
    assert "convert-copilot" in t
    low = " ".join(t.lower().split())
    # The port must be framed as a transform, so it does not read as contradicting
    # ADR-0002's refusal to author rules.
    assert "not authoring" in low or "transform, not authoring" in low
    # stdout/stderr split is what makes capture-then-mv safe here
    assert "notes to stderr" in low


# ---- cross-ecosystem + grounding regressions -------------------------------
# Every test below pins a defect found by running the skill end-to-end on a
# PHP/Laravel repo. Each one reproduced on the pre-fix code.


def test_heading_slug_uses_link_display_text_not_target():
    # GitHub slugs the RENDERED heading, so the link target is not part of the
    # anchor. Slugging the raw source folded the URL in and every intra-doc link
    # to such a heading was reported BROKEN_ANCHOR.
    assert lib.heading_slugs("## A [b](c/d.md)\n") == ["a-b"]
    # the heading that actually failed: the em dash is dropped, so the two spaces
    # that flanked it become the doubled '-' -- and the target is gone entirely.
    assert lib.heading_slugs("## C. Security — [`SECURITY.md`](sec.md)\n") == [
        "c-security--securitymd"
    ]
    # an image contributes no text content at all (<img> has none)
    assert lib.heading_slugs("## ![alt](x.png)\n") == [""]
    # angle-bracket and titled targets take the same path
    assert lib.heading_slugs('## A [b](<c d.md> "t")\n') == ["a-b"]


def test_heading_slug_leaves_plain_and_bracketless_headings_alone():
    # the fix must not touch headings that never had inline links
    assert lib.heading_slugs("## Plain Heading\n") == ["plain-heading"]
    assert lib.heading_slugs("## `code` and *em*\n") == ["code-and-em"]
    # an unmatched '[' is not a link and must survive as literal text
    assert lib.heading_slugs("## A [b\n") == ["a-b"]


def test_count_claim_requires_the_number_to_start_a_token():
    # "k6" and "8.4" are not claims about how many things are in the repo.
    assert list(lib.iter_count_claims("k6 stress tests live in k6/\n")) == []
    assert list(lib.iter_count_claims("PHP 8.4 classes are final by default\n")) == []
    # nor is a SECTION REFERENCE -- found by this gate firing on this repo's own
    # stamped update-docs skill ("the §5 pointer rules" read as 5 rules). `§` is not
    # a \w character, so the original guard let it through. Neither is groundable:
    # the author never claimed a quantity.
    assert list(lib.iter_count_claims("every §5 pointer rules mention targets it\n")) == []
    assert list(lib.iter_count_claims("see #3 files for the list\n")) == []
    # a real count is still caught
    claims = list(lib.iter_count_claims("This repo has 12 rules today\n"))
    assert [(c[1], c[2]) for c in claims] == [("12", "rules")]
    # and bold-wrapped counts keep working
    claims = list(lib.iter_count_claims("**42** files changed\n"))
    assert [(c[1], c[2]) for c in claims] == [("42", "files")]


def test_secret_globs_are_one_wildcard_in_ask_not_an_enumeration_in_deny():
    perms = lib.plan_project_permissions(["js"])["permissions"]
    # ONE glob. The enumeration this replaced needed 19 entries and still leaked:
    # `.env.local` was reached only after `**/*.env` was found not to cover it, and
    # `.env.uat` / `.env.preview` were never reached at all.
    assert "Read(**/.env*)" in perms["ask"]
    assert "Edit(**/.env*)" in perms["ask"]
    env_rules = [r for r in perms["ask"] if ".env" in r]
    assert env_rules == ["Read(**/.env*)", "Edit(**/.env*)"], env_rules
    # `**/*.env` was weighed and dropped: `.env*` already covers plain `.env`, so it
    # would only have added the `foo.env` spelling (docker `env_file:`, GitLab dotenv).
    assert not any(r.endswith("*.env)") for v in perms.values() for r in v)


def test_settings_plan_supports_php_and_keeps_npx_out_of_a_php_repo():
    plan = lib.plan_project_permissions(["php"])["permissions"]
    assert "Bash(composer install:*)" in plan["allow"]
    assert "Bash(vendor/bin/phpstan:*)" in plan["allow"]
    # lockfile- and schema-mutating commands are ask, not allow
    assert "Bash(composer update:*)" in plan["ask"]
    assert "Bash(php artisan migrate:*)" in plan["ask"]
    assert "Bash(composer update:*)" not in plan["allow"]
    # composer's registry-credentials file prompts
    assert "Read(**/auth.json)" in plan["ask"]
    # `npx:*` is js-specific AND opt-in: absent here, absent from a default js plan,
    # present only when the operator asks for it
    assert "Bash(npx:*)" not in plan["ask"]
    assert "Bash(npx:*)" not in lib.plan_project_permissions(["js"])["permissions"]["ask"]
    assert "Bash(npx:*)" in lib.plan_project_permissions(["js"], ask_npx=True)["permissions"]["ask"]


def test_deps_detect_ignores_vendored_manifests(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "composer.json", '{"require": {"laravel/framework": "^12.0"}}')
    _seed(tmp_path, "composer.lock", "{}")
    _seed(tmp_path, "artisan", "#!/usr/bin/env php\n")
    # a PHP repo's vendor/ tree carries dozens of package.json files belonging to
    # OTHER projects; treating them as this repo's workspace roots produced a
    # settings plan for an ecosystem the repo does not build.
    _seed(tmp_path, "vendor/acme/pkg/package.json", '{"name": "acme"}')
    _seed(tmp_path, "node_modules/x/package.json", '{"name": "x"}')
    rc = cli.main(["deps-detect", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert {e["name"] for e in out["ecosystems"]} == {"php"}
    php = out["ecosystems"][0]
    assert php["manager"] == "composer"
    assert php["tier0_rule"] == "laravel"
    assert len(php["workspaces"]) == 1
    assert php["lockfiles"] and php["lockfiles"][0].endswith("composer.lock")


def test_deps_detect_only_reports_lockfiles_that_exist(tmp_path, capsys):
    cli = _load_cli()
    # a package.json with no lockfile beside it must not yield a phantom path
    _seed(tmp_path, "package.json", '{"name": "a"}')
    _seed(tmp_path, "sub/package.json", '{"name": "b"}')
    _seed(tmp_path, "sub/pnpm-lock.yaml", "lockfileVersion: 9\n")
    rc = cli.main(["deps-detect", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    js = next(e for e in out["ecosystems"] if e["name"] == "js")
    assert [pathlib.Path(p).name for p in js["lockfiles"]] == ["pnpm-lock.yaml"]
    assert all(pathlib.Path(p).is_file() for p in js["lockfiles"])
    # and the manager follows the lockfile that is actually there
    assert js["manager"] == "pnpm"


def test_script_citations_are_scoped_to_their_runner():
    text = "Run `composer run test` and `npm run build`.\n"
    assert list(lib.iter_script_citations(text)) == [
        (1, "composer", "test"),
        (1, "npm", "build"),
    ]
    # a repo with only composer.json must not have its npm citations judged
    findings = lib.check_instructions(text, lambda p, n: True, known_scripts={"composer": {"test"}})
    assert findings == []
    # and an undefined composer script is still reported, named by its runner
    findings = lib.check_instructions(
        text, lambda p, n: True, known_scripts={"composer": {"other"}}
    )
    assert [(f[1], f[3]) for f in findings] == [
        ("UNDEFINED_SCRIPT", "composer run test is not a defined script")
    ]


def test_known_scripts_still_accepts_a_bare_set_as_the_npm_family():
    # backward compatibility: every pre-existing caller passed a plain set
    text = "Run `npm run build`.\n"
    assert lib.check_instructions(text, lambda p, n: True, known_scripts={"build"}) == []
    findings = lib.check_instructions(text, lambda p, n: True, known_scripts={"other"})
    assert [f[1] for f in findings] == ["UNDEFINED_SCRIPT"]


def test_check_instructions_reads_composer_scripts(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "composer.json", '{"scripts": {"test": "pest"}}')
    rules = _seed(tmp_path, ".claude/rules/r.md", "---\npaths:\n  - '**/*.php'\n---\n\nx\n")
    _seed(tmp_path, "app/Thing.php", "<?php\n")
    ok = _seed(
        tmp_path, ".claude/rules/ok.md", "---\npaths:\n  - 'app/**'\n---\n\n`composer run test`\n"
    )
    assert cli.main(["check-instructions", str(ok), "--repo-root", str(tmp_path)]) == 0
    bad = _seed(
        tmp_path, ".claude/rules/bad.md", "---\npaths:\n  - 'app/**'\n---\n\n`composer run nope`\n"
    )
    assert cli.main(["check-instructions", str(bad), "--repo-root", str(tmp_path)]) == 1
    assert "UNDEFINED_SCRIPT" in capsys.readouterr().out
    assert rules.is_file()


def test_check_instructions_skips_vendored_files_in_its_index(tmp_path, capsys):
    cli = _load_cli()
    # a rule scoped to a path that exists ONLY inside vendor/ can never fire on
    # first-party code, so the glob is dead even though the walk finds a match.
    _seed(tmp_path, "vendor/acme/src/Thing.php", "<?php\n")
    rule = _seed(tmp_path, ".claude/rules/r.md", "---\npaths:\n  - 'vendor/**'\n---\n\nx\n")
    assert cli.main(["check-instructions", str(rule), "--repo-root", str(tmp_path)]) == 1
    assert "DEAD_GLOB" in capsys.readouterr().out


def test_check_docs_distinguishes_a_missing_captures_flag_from_a_bad_capture(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "docs/a.md", "# A\n\n```text capture=plan\nFiles to write:\n  ~/x\n```\n")
    # no --captures at all: the doc may be perfectly correct, the INVOCATION is not
    rc, codes, lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 1 and codes == ["CAPTURES_NOT_CHECKED"]
    assert "--captures" in lines[0]
    # with the flag and a matching capture the same doc is clean
    _cap(tmp_path, "plan", "Files to write:\n  ~/x\n")
    caps = str(tmp_path / "docs" / ".onboard-captures")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--captures", caps])
    assert rc == 0 and codes == []


def test_cli_usage_banner_lists_every_implemented_verb():
    # a banner that omits half the verbs sends the operator to read the source
    src = (SCRIPTS / "onboard.py").read_text(encoding="utf-8")
    banner = src.split('"""')[1]
    verbs = set(re.findall(r'if cmd == "([a-z-]+)"', src))
    assert verbs  # guard against the regex silently matching nothing
    for verb in sorted(verbs):
        assert "onboard.py " + verb in banner, verb


def test_illustrative_marker_exempts_a_mock_table_from_citation_checks():
    # `illustrative` exempts a fence via its info string, but a markdown table has
    # none -- so a template's mock report table was four UNRESOLVED_CITATION errors.
    mock = (
        "## Final Report\n\n"
        "<!-- illustrative -->\n"
        "| Thread | Action |\n"
        "|---|---|\n"
        "| `file.php:42` | FIXED |\n"
        "| `service.php:15` | 7 files touched |\n"
        "\n"
        "And a real one: `onboard_lib.py:1`\n"
    )
    # the mock block contributes nothing...
    cited = [(p, n) for _, p, n in lib.iter_citations(mock)]
    assert cited == [("onboard_lib.py", 1)]
    # ...including its numbers, which are not claims about this repo
    assert list(lib.iter_count_claims(mock)) == []


def test_illustrative_marker_scope_ends_at_the_blank_line():
    # the marker must not be able to silence the rest of the file
    text = "<!-- illustrative -->\n| `mock.php:1` |\n\n| `real.php:2` |\n"
    assert [p for _, p, _ in lib.iter_citations(text)] == ["real.php"]


def test_check_docs_does_not_demand_provenance_in_the_frozen_archive_tier(tmp_path, capsys):
    cli = _load_cli()
    block = "# A\n\n```text\nFiles to write:\n  ~/x\n```\n"
    # the IA declares docs/archive/** frozen -- never edited -- so requiring a tag
    # there asked for an edit the same skill forbids.
    _seed(tmp_path, "docs/archive/old.md", block)
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []
    # the identical block in a live tier is still caught
    _seed(tmp_path, "docs/manual/live.md", block)
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 1 and codes == ["UNTAGGED_OUTPUT"]


def test_check_docs_still_reports_broken_links_inside_the_archive_tier(tmp_path, capsys):
    cli = _load_cli()
    # only grounding is skipped: a moved target still needs the link rebased
    _seed(tmp_path, "docs/archive/old.md", "# A\n\nsee [gone](./nope.md)\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 1 and "BROKEN_LINK" in codes


def test_existing_ecosystems_keep_every_allow_and_gain_only_secret_denies():
    """The php/ask restructure must not take anything away from js, rust, dotnet or
    swift beyond the one deliberate move of `npx:*` into the js entry."""
    for eco in ("js", "rust", "dotnet", "swift"):
        perms = lib.plan_project_permissions([eco])["permissions"]
        # every ecosystem's own build/test commands survive
        for cmd in lib._ECOSYSTEM_ALLOW[eco]:
            assert "Bash(%s)" % cmd in perms["allow"], (eco, cmd)
        # the baseline git guards survive in both tool forms
        for rule in ("Bash(git reset:*)", "PowerShell(git reset:*)"):
            assert rule in perms["deny"], (eco, rule)
        assert "Bash(git rm:*)" in perms["ask"], eco
    # `npx:*` is js-only AND opt-in: never in a default plan, and ask_npx on a
    # non-js repo adds nothing
    for eco in ("js", "rust", "dotnet", "swift", "php"):
        assert "Bash(npx:*)" not in lib.plan_project_permissions([eco])["permissions"]["ask"], eco
        if eco != "js":
            perms = lib.plan_project_permissions([eco], ask_npx=True)["permissions"]
            assert "Bash(npx:*)" not in perms["ask"], eco
    js = lib.plan_project_permissions(["js"], ask_npx=True)["permissions"]["ask"]
    assert "Bash(npx:*)" in js and "PowerShell(npx:*)" in js


def test_every_ask_and_deny_rule_the_planner_can_emit_has_a_reason():
    """A rule nobody can explain at the prompt is a rule nobody can defend: the
    reasons map must cover every body across every ecosystem, the baseline and the
    opt-in, so `--explain` never prints "(no reason recorded)" for a shipped rule."""
    bodies = set(lib._BASELINE_ASK) | set(lib._BASELINE_DENY) | {lib._NPX_ASK}
    for rules in lib._ECOSYSTEM_ASK.values():
        bodies.update(rules)
    missing = sorted(b for b in bodies if b not in lib._RULE_REASONS)
    assert missing == [], missing
    everything = lib.plan_project_permissions(list(lib._ECOSYSTEM_ALLOW), ask_npx=True)
    text = lib.explain_permissions(everything)
    assert "(no reason recorded)" not in text
    assert text.startswith(lib.ASK_COST)
    assert "human-only prompt" in lib.ASK_COST and "classifier cannot clear" in lib.ASK_COST


def test_settings_plan_explain_and_ask_npx_flags(tmp_path, capsys):
    cli = _load_cli()
    rc = cli.main(["settings-plan", str(tmp_path), "--ecosystem", "js", "--explain"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith(lib.ASK_COST)
    assert "\ndeny  git reset:*" in out and "\nask   git rm:*" in out
    assert "npx:*" not in out  # opt-in, so absent from the default explanation
    # collapsed to one line per body: no PowerShell twin printed separately
    assert "PowerShell(" not in out
    # allow rules are never explained
    assert "npm run:*" not in out

    rc = cli.main(["settings-plan", str(tmp_path), "--ecosystem", "js", "--ask-npx", "--explain"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "\nask   npx:*" in out and "opt-in" in out

    rc = cli.main(["settings-plan", str(tmp_path), "--ecosystem", "js", "--ask-npx"])
    out = capsys.readouterr().out
    assert rc == 0
    plan = json.loads(out)
    assert "Bash(npx:*)" in plan["permissions"]["ask"]


def test_link_free_headings_slug_exactly_as_before():
    """The inline-render step must be a no-op for any heading without a link or image
    -- that is the whole existing corpus, so a change here would be a silent regression."""
    cases = {
        "## Plain Heading\n": ["plain-heading"],
        "## `code` span\n": ["code-span"],
        "## Café naïve\n": ["café-naïve"],
        "## dup\n## dup\n## dup-1\n": ["dup", "dup-1", "dup-1-1"],
        "## A_B_C\n": ["a_b_c"],
        "## 100% done\n": ["100-done"],
        "## CJK 中文\n": ["cjk-中文"],
        "## with-hyphen and space\n": ["with-hyphen-and-space"],
    }
    for text, want in cases.items():
        assert lib.heading_slugs(text) == want, text


def test_genuine_count_claims_still_fire_after_the_token_boundary_fix():
    """The `(?<![\\w.])` guard must only remove digits plucked out of identifiers and
    versions -- every real count keeps reporting."""
    cases = {
        "This repo has 12 rules today\n": [("12", "rules")],
        "**42** files changed\n": [("42", "files")],
        "there are 3 call sites\n": [("3", "sites")],
        "7 tests cover it\n": [("7", "tests")],
        "1,234 entries in the index\n": [("1234", "entries")],
        "two tiers exist\n": [],
    }
    for text, want in cases.items():
        got = [(c[1], c[2]) for c in lib.iter_count_claims(text)]
        assert got == want, (text, got)


def test_deps_detect_reports_python_with_the_manager_its_lockfile_implies(tmp_path, capsys):
    cli = _load_cli()
    # a PEP 621 project managed by uv -- telling the agent to run `pip` here sends it
    # to a command that will not reproduce the locked environment.
    _seed(tmp_path, "pyproject.toml", '[project]\nname = "x"\nversion = "0.1.0"\n')
    _seed(tmp_path, "uv.lock", "version = 1\n")
    rc = cli.main(["deps-detect", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    eco = next(e for e in out["ecosystems"] if e["name"] == "python")
    assert eco["manager"] == "uv"
    assert [pathlib.Path(p).name for p in eco["lockfiles"]] == ["uv.lock"]
    assert eco["tier0_rule"] == "none"
    assert len(eco["workspaces"]) == 1


def test_deps_detect_python_falls_back_to_pip_and_flags_django(tmp_path, capsys):
    cli = _load_cli()
    # legacy layout, no lockfile of any manager -> pip; manage.py -> the django tier0
    _seed(tmp_path, "setup.py", "from setuptools import setup\nsetup()\n")
    _seed(tmp_path, "manage.py", "#!/usr/bin/env python\n")
    rc = cli.main(["deps-detect", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    eco = next(e for e in out["ecosystems"] if e["name"] == "python")
    assert eco["manager"] == "pip"
    assert eco["lockfiles"] == []  # nothing invented when no lockfile exists
    assert eco["tier0_rule"] == "django"


def test_settings_plan_python_separates_running_tests_from_mutating_the_lock():
    plan = lib.plan_project_permissions(["python"])["permissions"]
    for rule in (
        "Bash(uv sync:*)",
        "Bash(uv run pytest:*)",
        "Bash(pytest:*)",
        "Bash(ruff check:*)",
        "Bash(mypy:*)",
    ):
        assert rule in plan["allow"], rule
    for rule in (
        "Bash(uv add:*)",
        "Bash(uv lock:*)",
        "Bash(pip install:*)",
        "Bash(alembic upgrade:*)",
    ):
        assert rule in plan["ask"], rule
        assert rule not in plan["allow"], rule
    # bare `uv run:*` would be a blanket shell grant -- unlike `npm run <script>`, which
    # package.json bounds, `uv run <anything>` executes an arbitrary command.
    assert "Bash(uv run:*)" not in plan["allow"]
    assert "Bash(uv run:*)" not in plan["ask"]
    # registry credentials prompt
    for glob in ("**/.pypirc", "**/pip.conf", "**/uv.toml"):
        assert "Read(%s)" % glob in plan["ask"], glob


def test_deps_detect_error_message_names_every_manifest_it_looks_for(tmp_path, capsys):
    cli = _load_cli()
    _seed(tmp_path, "README.md", "# nothing here")
    assert cli.main(["deps-detect", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    # an operator who hits this must be able to tell whether their ecosystem is even
    # a candidate -- the message previously omitted composer.json and pyproject.toml
    for manifest in (
        "package.json",
        "composer.json",
        "pyproject.toml",
        "Cargo.toml",
        "Package.swift",
    ):
        assert manifest in err, manifest
    assert "Traceback" not in err


def test_check_docs_flags_a_manual_page_that_only_shows_commands(tmp_path, capsys):
    cli = _load_cli()
    # Observed on a real run: ten bash fences, one illustrative block, zero captures,
    # and check-docs clean -- the grounding checks can only see output that is PRESENT
    # and untagged, never output that is absent.
    _seed(tmp_path, "docs/manual/cli.md", "# CLI\n\n```bash\nuv run pytest\n```\n")
    rc, codes, lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == ["NO_SHOWCASE"]  # advisory, never fails the gate
    assert "tells instead of showing" in lines[0]
    # one illustrative block is enough to clear it -- the page is showing something
    _seed(
        tmp_path,
        "docs/manual/cli.md",
        "# CLI\n\n```bash\nuv run pytest\n```\n\n```text illustrative\n5 passed\n```\n",
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


def test_no_showcase_skips_index_pages_prose_pages_and_the_frozen_tier(tmp_path, capsys):
    cli = _load_cli()
    block = "# X\n\n```bash\nmake up\n```\n"
    _seed(tmp_path, "docs/manual/README.md", block)  # the manual index, not a page
    _seed(tmp_path, "docs/manual/prose.md", "# X\n\nNo fences at all.\n")
    _seed(tmp_path, "docs/archive/manual/old.md", block)  # frozen: never edited
    _seed(tmp_path, "docs/internals/mech.md", block)  # not a consumer page
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


def test_check_docs_flags_an_absolute_home_path_in_a_committed_doc(tmp_path, capsys):
    cli = _load_cli()
    # `redact` normalizes these out of a capture, but an ADOPTED page never passes
    # through it -- §3.6 moves a repo's existing docs verbatim.
    for shape in ("/home/someone/proj", "/Users/someone/proj", "C:\\Users\\someone\\proj"):
        _seed(tmp_path, "docs/internals/a.md", "# A\n\nWorking dir: `%s`\n" % shape)
        rc, codes, lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
        assert rc == 0 and codes == ["LEAKED_PATH"], shape
        assert "rewrite as a repo-relative path" in lines[0]
    # a repo-relative path or a tilde is fine
    _seed(tmp_path, "docs/internals/a.md", "# A\n\nSee `docs/manual/` and `~/.claude/`.\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


def test_check_docs_flags_an_adr_that_is_one_only_by_filename(tmp_path, capsys):
    cli = _load_cli()
    # Observed on a real run: a dated spec moved into docs/adr/, given an `# ADR-0001:`
    # heading, and otherwise left as the spec -- two statuses, two dates, no sections.
    _seed(tmp_path, "docs/adr/0001-thing.md", "# ADR-0001: Thing\n\n- **Status:** accepted\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0
    assert sorted(codes) == ["ADR_NAMING", "ADR_SHAPE"]
    # correctly named AND correctly shaped -> clean
    _seed(
        tmp_path,
        "docs/adr/ADR-0001-thing.md",
        "# ADR-0001: Thing\n\n- **Status:** accepted\n\n## Context\nx\n## Decision\ny\n"
        "## Consequences\nz\n",
    )
    (tmp_path / "docs/adr/0001-thing.md").unlink()
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


def test_adr_checks_exempt_the_template_and_the_index(tmp_path, capsys):
    cli = _load_cli()
    # the scaffolded ADR-TEMPLATE.md carries <angle> placeholders, not sections, and
    # docs/adr/README.md is an index -- neither is a decision record
    _seed(tmp_path, "docs/adr/ADR-TEMPLATE.md", "# ADR-NNNN: <decision title>\n")
    _seed(tmp_path, "docs/adr/README.md", "# Architecture Decision Records\n\nIndex.\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


_ADR_OK = (
    "# ADR-%s: T\n\n- **Status:** accepted\n\n## Context\nx\n## Decision\ny\n## Consequences\nz\n"
)


def test_adr_index_drift_is_present_based(tmp_path, capsys):
    cli = _load_cli()
    # no index README at all -> a minimal repo keeps no index; nothing to drift from
    _seed(tmp_path, "docs/adr/ADR-0001-thing.md", _ADR_OK % "0001")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []
    # an index exists but carries no row for the record -> the tier's only ToC lies
    _seed(tmp_path, "docs/adr/README.md", "# ADRs\n\n| ADR | Title |\n| --- | --- |\n")
    rc, codes, lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == ["ADR_INDEX_DRIFT"]
    assert "no [ADR-0001] row" in lines[0]
    # a row present -> clean (the reverse direction, a rowed file gone, is BROKEN_LINK)
    _seed(
        tmp_path,
        "docs/adr/README.md",
        "# ADRs\n\n| [ADR-0001](ADR-0001-thing.md) | T |\n",
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


def test_adr_dangling_supersede_pointer_is_flagged(tmp_path, capsys):
    cli = _load_cli()
    # "amended by ADR-0099" with no ADR-0099-*.md -> the one maintained edit dangles
    body = _ADR_OK % "0001" + "\nStatus note: section 4 amended by\nADR-0099.\n"
    _seed(tmp_path, "docs/adr/ADR-0001-thing.md", body)
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == ["ADR_DANGLING_SUPERSEDE"]
    # the pointer resolves once the superseding record exists -> clean, including
    # the wrapped-and-linked form a real status transition uses
    body = _ADR_OK % "0001" + "\nStatus note: section 4 amended by\n[ADR-0099](ADR-0099-x.md).\n"
    _seed(tmp_path, "docs/adr/ADR-0001-thing.md", body)
    _seed(tmp_path, "docs/adr/ADR-0099-x.md", _ADR_OK % "0099")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []
    # wrapped across a line and linked, like a real status transition, still matches;
    # a record quoting its OWN transition is not a dangling pointer
    solo = _ADR_OK % "0002" + "\nThis section was superseded by ADR-0002 itself.\n"
    _seed(tmp_path, "docs/adr/ADR-0002-self.md", solo)
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


# ---- Long-run state + per-page gate scoping (3-4h brownfield onboarding) -----
#
# A brownfield pass is a multi-hour run whose operator confirmations lived only in
# the model's context, so a compaction restarted it from detection. These cover the
# durable record and the two scoping flags the per-page authoring loop needs.


def _run_set(cli, capsys, path, args):
    """Apply one run-set mutation and write the result back (capture-then-mv, the
    idiom SKILL.md uses). Returns the parsed record."""
    rc = cli.main(["run-set", str(path)] + list(args))
    out = capsys.readouterr().out
    assert rc == 0, out
    path.write_text(out, encoding="utf-8")
    return json.loads(out)


def _fresh_run(cli, capsys, tmp_path, keys=("install", "usage")):
    rc = cli.main(["run-init", "20260729-120000", str(tmp_path), "--mode", "default"])
    out = capsys.readouterr().out
    assert rc == 0
    p = tmp_path / "run.json"
    p.write_text(out, encoding="utf-8")
    if keys:
        _run_set(cli, capsys, p, ["--add", ",".join(keys), "--kind", "surface"])
    return p


def test_run_init_writes_a_valid_v1_record(tmp_path, capsys):
    cli = _load_cli()
    p = _fresh_run(cli, capsys, tmp_path, keys=())
    rec = json.loads(p.read_text(encoding="utf-8"))
    assert rec["schema"] == lib.RUN_SCHEMA
    assert rec["phase"] == "detect" and rec["items"] == [] and rec["confirmed"] == {}


def test_run_state_survives_reregistration_of_finished_items(tmp_path, capsys):
    # THE resume property: after a compaction the skill re-runs detection and
    # re-registers every surface. A done page must not silently revert to pending
    # (that is what made a long run restart from zero).
    cli = _load_cli()
    p = _fresh_run(cli, capsys, tmp_path)
    _run_set(cli, capsys, p, ["--mark", "usage", "--state", "done"])
    rec = _run_set(cli, capsys, p, ["--add", "install,usage,security", "--kind", "surface"])
    states = {it["key"]: it["state"] for it in rec["items"]}
    assert states == {"install": "pending", "usage": "done", "security": "pending"}


def test_run_next_prefers_an_interrupted_item_then_pending(tmp_path, capsys):
    # A run that died mid-page resumes THAT page rather than skipping it.
    cli = _load_cli()
    p = _fresh_run(cli, capsys, tmp_path)
    _run_set(cli, capsys, p, ["--mark", "usage", "--state", "in-progress"])
    assert cli.main(["run-next", str(p)]) == 0
    assert capsys.readouterr().out.strip() == "usage"


def test_run_next_exit_3_when_only_parked_work_remains(tmp_path, capsys):
    # Parking one stubborn page must not block the rest of the run, and a parked
    # item is not actionable -- rc 3 is "no work left", distinct from success/error.
    cli = _load_cli()
    p = _fresh_run(cli, capsys, tmp_path)
    _run_set(cli, capsys, p, ["--mark", "install", "--state", "done"])
    _run_set(cli, capsys, p, ["--mark", "usage", "--state", "parked", "--note", "needs a live DB"])
    assert cli.main(["run-next", str(p)]) == 3
    assert capsys.readouterr().out == ""


def test_run_status_names_every_parked_item_and_its_reason(tmp_path, capsys):
    cli = _load_cli()
    p = _fresh_run(cli, capsys, tmp_path)
    _run_set(cli, capsys, p, ["--mark", "usage", "--state", "parked", "--note", "needs a live DB"])
    assert cli.main(["run-status", str(p)]) == 0
    out = capsys.readouterr().out
    assert "PARKED usage: needs a live DB" in out
    assert "1 pending, 1 parked" in out


def test_run_confirm_reads_a_file_not_an_inline_argument(tmp_path, capsys):
    # A confirmed detection / move plan is far too big for a shell argument, and
    # quoting it inline is how a plan gets silently truncated.
    cli = _load_cli()
    p = _fresh_run(cli, capsys, tmp_path, keys=())
    payload = tmp_path / "detect.json"
    payload.write_text(json.dumps({"ecosystem": "php", "manager": "composer"}), encoding="utf-8")
    rec = _run_set(cli, capsys, p, ["--confirm", "detection=" + str(payload)])
    assert rec["confirmed"]["detection"]["manager"] == "composer"
    # and a phase advance carries confirmations forward rather than dropping them
    rec = _run_set(cli, capsys, p, ["--phase", "stamp"])
    assert rec["phase"] == "stamp" and "detection" in rec["confirmed"]
    assert "detect" in rec["phases_done"]


@pytest.mark.parametrize(
    "body",
    ['{"schema": 99, "items": [], "confirmed": {}, "log": [], "phases_done": []}', "{not json"],
)
def test_malformed_run_record_fails_closed(tmp_path, capsys, body):
    # Never silently replaced with a fresh record: that discards the operator's
    # confirmations, the same fail-closed rule --sync applies to markers.
    cli = _load_cli()
    p = _seed(tmp_path, "run.json", body)
    assert cli.main(["run-status", str(p)]) == 2


def test_run_mark_on_an_unknown_key_is_an_error(tmp_path, capsys):
    # Caller and record disagreeing about what work exists is the drift this
    # record exists to detect; inventing the item would paper over it.
    cli = _load_cli()
    p = _fresh_run(cli, capsys, tmp_path)
    assert cli.main(["run-set", str(p), "--mark", "nosuch", "--state", "done"]) == 2


def test_run_state_error_is_not_reported_as_a_manifest_error(tmp_path, capsys):
    cli = _load_cli()
    p = _seed(tmp_path, "run.json", "{not json")
    cli.main(["run-status", str(p)])
    assert "RUN STATE ERROR" in capsys.readouterr().err


def test_check_docs_only_scopes_emission_but_keeps_error_severity(tmp_path, capsys):
    # The per-page loop MUST pass full roots + --only. Narrowing the root instead
    # downgrades a real broken link to a warning (severity keys on _within_roots),
    # so the gate would exit 0 on a broken page -- asserted in the next test.
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/a.md", "# A\n\n[gone](./missing.md)\n")
    _seed(tmp_path, "docs/manual/b.md", "# B\n\n[also gone](./nope.md)\n")
    rc, codes, lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 1 and codes == ["BROKEN_LINK", "BROKEN_LINK"]
    rc, codes, lines = _run_check(
        cli, capsys, [str(tmp_path / "docs")], ["--only", str(tmp_path / "docs/manual/a.md")]
    )
    assert rc == 1 and codes == ["BROKEN_LINK"]
    assert "a.md" in lines[0] and all("b.md" not in ln for ln in lines)


def test_narrowing_the_root_degrades_severity_which_only_does_not(tmp_path, capsys):
    # Pins the trap itself, so nobody "simplifies" --only into a single-file root.
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/a.md", "# A\n\n[gone](./missing.md)\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs/manual/a.md")])
    assert rc == 0 and codes == ["BROKEN_LINK"]  # warn: link target is outside the root
    rc, codes, _ = _run_check(
        cli, capsys, [str(tmp_path / "docs")], ["--only", str(tmp_path / "docs/manual/a.md")]
    )
    assert rc == 1 and codes == ["BROKEN_LINK"]  # error: full roots still resolve


def test_check_docs_no_tier_check_suppresses_only_the_tree_wide_sweep(tmp_path, capsys):
    # Mid-run an unauthored surface is expected, not a finding; per-file checks stay on.
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/a.md", "# A\n\n[gone](./missing.md)\n")
    cov = _seed(
        tmp_path,
        "cov.json",
        json.dumps([{"surface": "I", "slug": "install", "tier": "principal", "page": None}]),
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")], ["--coverage", str(cov)])
    assert rc == 1 and "EMPTY_TIER" in codes
    rc, codes, _ = _run_check(
        cli, capsys, [str(tmp_path / "docs")], ["--coverage", str(cov), "--no-tier-check"]
    )
    assert rc == 1 and "EMPTY_TIER" not in codes and codes == ["BROKEN_LINK"]


def test_check_docs_only_resolves_path_spellings(tmp_path, capsys):
    # `docs/./a.md` and a plain path name the same page.
    cli = _load_cli()
    _seed(tmp_path, "docs/manual/a.md", "# A\n\n[gone](./missing.md)\n")
    rc, codes, _ = _run_check(
        cli, capsys, [str(tmp_path / "docs")], ["--only", str(tmp_path / "docs/./manual/a.md")]
    )
    assert rc == 1 and codes == ["BROKEN_LINK"]


# ---- update-docs: the maintenance seam onboarding leaves behind ---------------
#
# update-docs is the skill that OUTLIVES onboarding -- onboard-repo runs once, this
# one runs for years. These pin the three gaps that made it weaker than the one-shot:
# it demanded a capture it had no tool to take, it never read the coverage record
# (so a PARKED surface was visible only to a command nobody re-runs), and it could
# not see a surface that had no page at all.


def test_update_docs_can_actually_run_what_it_prescribes():
    # §7.5 says "re-capture, never hand-edit" and names the redact verb. With no
    # python3/mv grant that is an instruction the skill cannot follow -- the same
    # class of defect as a check demanding an edit the IA forbids (ADR-0004).
    front = UPD.read_text(encoding="utf-8").split("---", 2)[1]
    assert "Bash(python3:*)" in front, "redact/check-docs need a python3 grant"
    assert "Bash(mv:*)" in front, "capture-then-mv needs mv"


def test_update_docs_hands_the_capture_run_to_the_operator():
    t = _norm(UPD)
    # it may PROPOSE a capture, but it carries no arbitrary-shell grant, so the
    # operator runs it -- exactly as onboard-repo §3.7 does
    assert "operator runs it" in t
    assert "redact" in t and "not a secret scanner" in t
    # and the honest failure mode: leave the stale block, never fake the evidence
    assert "leave the stale block alone and report it" in t


def test_update_docs_maintains_the_coverage_record():
    t = _norm(UPD)
    assert "docs/.onboard-coverage.json" in t
    assert "principal" in t and "deferred" in t
    # a parked surface must be RESTATED every run: onboard-repo --check is the
    # command nobody runs again, so a deferral would quietly become permanent
    assert "parked" in t
    assert "emptytier" in t  # _norm strips underscores: EMPTY_TIER -> emptytier
    # and the anti-cheat: flipping status to silence a finding is not a fix
    assert "never flip a status" in t


def test_update_docs_reports_a_missing_surface_but_never_authors_it():
    t = _norm(UPD)
    assert "report-only finding" in t
    # authoring needs a captured command this skill cannot run -> hand off
    assert "do not author the page here" in t
    assert "/batbelt:onboard-repo" in t
    # report-only in EVERY mode, so --apply cannot quietly close the contract
    assert "report-only in every mode" in t


def test_update_docs_grounding_gate_names_the_stamped_scripts():
    t = _norm(UPD)
    assert "check-docs" in t
    assert ".claude/skills/update-docs/scripts/check.py" in t
    # the --only trap, restated where a maintainer would actually hit it
    assert "run it unscoped" in t
    # a missing gate is announced, never silently skipped
    assert "never silently skip a gate" in t


def test_onboard_repo_stamps_the_helper_scripts_beside_update_docs():
    # onboard-repo's OWN SKILL.md carries no REPO SPECIFICS markers (it is the
    # stamper, not a stamped file), so _norm's parse_regions would fail on it.
    def flat(path):
        body = pathlib.Path(path).read_text(encoding="utf-8").lower()
        for ch in ("*", "_", "`"):
            body = body.replace(ch, "")
        return " ".join(body.split())

    t = flat(SKILL)
    # The recipes loop over the consuming skills rather than spelling each path out, so
    # assert the LOOP covers both -- pinning a literal `.claude/skills/update-docs/
    # scripts` broke the moment the --check recipe became a loop, while the instruction
    # it was standing in for was still correct.
    assert "for s in update-docs update-rules; do" in t
    assert ".claude/skills/$s/scripts" in t
    assert "check.py" in t
    # the gate script ships ALONE -- the onboarding verbs must not ride along
    # into a skill that runs for years (ADR-0008)
    assert "never onboard.py/onboardlib.py" in t
    # it is WHOLLY template-owned: no REPO SPECIFICS, so --sync replaces it
    # outright and preserve would fail closed on the absent markers
    assert "carries no repo specifics" in t
    # a pre-split stamp is MIGRATED, not left with both layouts side by side
    assert 'rm -f ".claude/skills/$s/scripts/onboard.py"' in t
    stamping = flat(ONBOARD / "references" / "stamping.md")
    assert "replaced outright" in stamping
    assert "do not run preserve on it" in stamping
    assert "never copy onboard.py/onboardlib.py" in stamping


STDLIB = {"copy", "json", "pathlib", "re", "sys", "posixpath", "xml.etree.ElementTree"}


def _all_imports(name):
    """Every module imported ANYWHERE in the file, via AST.

    Was a column-0 regex, and three evasions defeated it -- each one leaving check.py
    un-copyable into a stamped repo while the suite stayed green:
      `import pathlib, onboard_lib`   (regex captured only the first name)
      an indented `try: import onboard_lib`
      a function-local `import onboard_lib`
    Depth and position are exactly what must NOT matter here: a lazy import inside a
    function breaks the stamped copy at runtime rather than at import, which is worse.
    """
    tree = ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    assert found, name  # the walk must actually find something
    return found


def _toplevel_imports(name):  # retained name; now depth-independent
    return _all_imports(name)


def test_the_stamped_script_is_stdlib_only_with_no_sibling_import():
    # check.py is the ONLY file stamped into a maintained repo, so a plain `cp` of it
    # is sound only if it needs no sibling at all. This is strictly stronger than the
    # old pair's "imports nothing but each other" -- that one would still pass if
    # check.py reached back into onboard_lib, which would break every stamped repo.
    assert _toplevel_imports("check.py") <= STDLIB


def test_the_dependency_between_the_scripts_points_one_way():
    # onboard.py and onboard_lib.py may import check.py; the reverse would make the
    # stamped file un-copyable, and an import cycle would be the way it creeps back in.
    assert "check" in _toplevel_imports("onboard.py")
    assert "check" in _toplevel_imports("onboard_lib.py")
    assert _toplevel_imports("onboard.py") <= STDLIB | {"check", "onboard_lib"}
    assert _toplevel_imports("onboard_lib.py") <= STDLIB | {"check"}
