"""Regression tests for the review fixes on top of the cross-ecosystem change.

Every test here pins a defect found reviewing that change itself; each one
reproduced on the pre-fix branch. Kept in its own module so the fixes are
readable as one set -- `test_onboard_repo.py` already carries the change's own
suite.
"""

import fnmatch
import json
import pathlib
import re

from test_onboard_repo import (  # noqa: F401  (fixtures come via the helpers)
    ONBOARD,
    _load_cli,
    _run_check,
    _seed,
    lib,
)

# ---- root-relative exclusion: the citation/glob index ------------------------


def test_citation_index_excludes_relative_to_the_base_not_absolutely(tmp_path, capsys):
    cli = _load_cli()
    # A repo checked out under a directory named `build` had EVERY file skipped, because
    # the skip test read the ABSOLUTE path's parts. Both findings below were false, and
    # both are error-level, so the gate failed a correct repo.
    repo = tmp_path / "build" / "myrepo"
    _seed(repo, "app/Thing.php", "<?php\n")
    rule = _seed(
        repo, ".claude/rules/r.md", "---\npaths:\n  - 'app/**'\n---\n\nSee `Thing.php:1`.\n"
    )
    assert cli.main(["check-instructions", str(rule), "--repo-root", str(repo)]) == 0
    assert capsys.readouterr().out == ""
    # the same tree NOT under a build dir behaves identically -- that is the invariant
    plain = tmp_path / "plain"
    _seed(plain, "app/Thing.php", "<?php\n")
    rule2 = _seed(
        plain, ".claude/rules/r.md", "---\npaths:\n  - 'app/**'\n---\n\nSee `Thing.php:1`.\n"
    )
    assert cli.main(["check-instructions", str(rule2), "--repo-root", str(plain)]) == 0


def test_citation_index_still_skips_a_genuinely_vendored_tree(tmp_path, capsys):
    cli = _load_cli()
    # the fix must not weaken the exclusion it was derived from: a path that exists ONLY
    # under vendor/ can never fire on first-party code
    _seed(tmp_path, "vendor/acme/src/Thing.php", "<?php\n")
    rule = _seed(tmp_path, ".claude/rules/r.md", "---\npaths:\n  - 'vendor/**'\n---\n\nx\n")
    assert cli.main(["check-instructions", str(rule), "--repo-root", str(tmp_path)]) == 1
    assert "DEAD_GLOB" in capsys.readouterr().out


# ---- manifest walk: build output is not a dependency tree --------------------


def test_deps_detect_sees_a_manifest_under_a_build_output_dir(tmp_path, capsys):
    cli = _load_cli()
    # `build`/`dist`/`target` are build OUTPUT, not a dependency tree. Excluding them
    # from the MANIFEST walk made a repo whose only package.json sits there report no
    # ecosystem at all, which silently skips update-deps (SKILL.md §3.4).
    _seed(tmp_path, "build/app/package.json", '{"name": "a"}')
    rc = cli.main(["deps-detect", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert [e["name"] for e in out["ecosystems"]] == ["js"]


def test_deps_detect_does_not_count_a_built_copy_as_a_second_workspace(tmp_path, capsys):
    cli = _load_cli()
    # The first attempt at the fix above made build output a PEER of the real manifest,
    # which double-reported: `cargo package` leaves a full crate -- `[workspace]` section
    # and all -- under target/package/, and a publishable subpackage ships a
    # dist/package.json. Build output is a LAST RESORT, consulted only when the pattern
    # matched nothing outside it.
    cargo = '[workspace]\nmembers = ["."]\n\n[package]\nname = "c"\nversion = "0.1.0"\n'
    _seed(tmp_path, "Cargo.toml", cargo)
    _seed(tmp_path, "target/package/c-0.1.0/Cargo.toml", cargo)
    _seed(tmp_path, "package.json", '{"name": "root", "workspaces": ["packages/*"]}')
    _seed(tmp_path, "dist/package.json", '{"name": "root", "main": "index.js"}')
    _seed(tmp_path, "build/lib/package.json", '{"name": "root"}')
    rc = cli.main(["deps-detect", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert sum(1 for e in out["ecosystems"] if e["name"] == "rust") == 1
    js = next(e for e in out["ecosystems"] if e["name"] == "js")
    assert len(js["workspaces"]) == 1
    assert pathlib.Path(js["workspaces"][0]["root"]).name == tmp_path.name


def test_deps_detect_still_ignores_a_dependency_tree_manifest(tmp_path, capsys):
    cli = _load_cli()
    # the narrower exclusion list must still cover what it was introduced for
    _seed(tmp_path, "composer.json", '{"require": {}}')
    _seed(tmp_path, "vendor/acme/pkg/package.json", '{"name": "acme"}')
    _seed(tmp_path, "node_modules/x/package.json", '{"name": "x"}')
    _seed(tmp_path, ".venv/lib/site-packages/pkg/setup.py", "setup()\n")
    rc = cli.main(["deps-detect", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert {e["name"] for e in out["ecosystems"]} == {"php"}


# ---- agent working directories are not documentation -------------------------


def test_an_agent_working_directory_is_excluded_from_the_docs_walk(tmp_path, capsys):
    cli = _load_cli()
    # `docs/superpowers/{plans,specs}` is a PLUGIN's working directory: tool-written
    # scratch, in no docs tier, deliberately quoting pre-sanitization sources.
    # test/check_clean.sh already carves out the same names. Grounding it reported 47
    # findings nobody would act on, which is the noise that gets a gate switched off.
    _seed(tmp_path, "docs/superpowers/plans/p.md", "# Plan\n\n```text\nout\n  x\n```\n")
    _seed(tmp_path, "docs/superpowers/specs/s.md", "# Spec\n\nran in /home/jack/proj\n")
    _seed(tmp_path, ".superpowers/scratch.md", "# S\n\n```text\nout\n  x\n```\n")
    _seed(tmp_path, "docs/manual/real.md", "# Real\n\n```text\nout\n  x\n```\n")
    _rc, codes, lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
    # only the genuine manual page is reported
    assert [ln.split("\t")[2] for ln in lines if ln.split("\t")[1] == "UNTAGGED_OUTPUT"] == [
        str(tmp_path / "docs/manual/real.md") + ":3"
    ]
    assert "LEAKED_PATH" not in codes


def test_the_exclusion_is_a_directory_not_a_filename_substring(tmp_path, capsys):
    cli = _load_cli()
    # a real docs page ABOUT superpowers is still documentation and still checked --
    # excluding on a name substring would have silently dropped it
    _seed(tmp_path, "docs/internals/superpowers-notes.md", "# S\n\n```text\nout\n  x\n```\n")
    _rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert codes == ["UNTAGGED_OUTPUT"]


def test_a_working_directory_supplies_no_citation_grounding(tmp_path, capsys):
    cli = _load_cli()
    # the citation/glob index derives its skip list from the docs walk's, so scratch
    # notes cannot resolve a shorthand citation either -- the two must not disagree
    _seed(tmp_path, "docs/superpowers/plans/scratch.md", "line1\nline2\n")
    rule = _seed(
        tmp_path, ".claude/rules/r.md", "---\npaths:\n  - 'docs/**'\n---\n\nSee `scratch.md:1`.\n"
    )
    assert cli.main(["check-instructions", str(rule), "--repo-root", str(tmp_path)]) == 1
    assert "UNRESOLVED_CITATION" in capsys.readouterr().out


# ---- root-relative tiers: archive / manual / adr ----------------------------


def test_frozen_tier_is_keyed_to_the_scanned_root_not_the_checkout_path(tmp_path, capsys):
    cli = _load_cli()
    # A repo living under a directory named `archive` had grounding SILENTLY disabled on
    # its live pages -- the dangerous direction: the gate turns off without saying so.
    block = "# A\n\n```text\nFiles to write:\n  ~/x\n```\n"
    _seed(tmp_path / "archive" / "myrepo", "docs/manual/live.md", block)
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "archive" / "myrepo" / "docs")])
    assert rc == 1 and codes == ["UNTAGGED_OUTPUT"]
    # and the real frozen tier is still exempt
    _seed(tmp_path / "plain", "docs/archive/old.md", block)
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "plain" / "docs")])
    assert rc == 0 and codes == []


def test_manual_and_adr_tiers_are_keyed_to_the_scanned_root(tmp_path, capsys):
    cli = _load_cli()
    # a checkout under `adr/` reported every page as a malformed decision record, and
    # one under `manual/` reported internals pages for showing no output
    _seed(tmp_path / "adr" / "myrepo", "docs/manual/usage.md", "# Usage\n\nprose only\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "adr" / "myrepo" / "docs")])
    assert rc == 0 and codes == []
    _seed(tmp_path / "manual" / "myrepo", "docs/internals/mech.md", "# M\n\n```bash\nls\n```\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "manual" / "myrepo" / "docs")])
    assert rc == 0 and codes == []


def test_tier_survives_being_named_directly_as_the_root(tmp_path, capsys):
    cli = _load_cli()
    # Taking relparts from the walk root alone LOST the tier whenever the operator named
    # it: `check-docs docs/archive` made relparts ('old.md',), so the frozen exemption
    # stopped applying to the very tier it protects. The tier is a fact about the docs
    # tree, so the root's own tier components have to travel with each file.
    _seed(tmp_path, "docs/archive/old.md", "# A\n\n```text\nFiles:\n  x\n```\n")
    _seed(tmp_path, "docs/manual/p.md", "# P\n\n```bash\nls\n```\n")
    _seed(tmp_path, "docs/adr/0001-bad.md", "# Old decision\n\nno sections\n")
    # naming each tier DIRECTLY must match what scanning the parent reports
    for root, want in (
        ("docs/archive", []),
        ("docs/manual", ["NO_SHOWCASE"]),
        ("docs/adr", ["ADR_NAMING", "ADR_SHAPE"]),
    ):
        _rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / root)])
        assert sorted(codes) == sorted(want), root
    # and so must naming a single FILE
    for rel, want in (
        ("docs/archive/old.md", []),
        ("docs/manual/p.md", ["NO_SHOWCASE"]),
        ("docs/adr/0001-bad.md", ["ADR_NAMING", "ADR_SHAPE"]),
    ):
        _rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / rel)])
        assert sorted(codes) == sorted(want), rel


def test_a_checkout_under_a_tier_named_directory_contributes_no_tier(tmp_path, capsys):
    cli = _load_cli()
    # the other half of the same rule: only the TAIL of the named root counts, so a repo
    # living under a dir called `archive` must not have its live pages treated as frozen
    _seed(tmp_path / "archive" / "myrepo", "docs/manual/live.md", "# A\n\n```text\nout\n  x\n```\n")
    _rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "archive" / "myrepo" / "docs")])
    assert "UNTAGGED_OUTPUT" in codes


def test_adr_checks_exempt_the_frozen_archive_tier(tmp_path, capsys):
    cli = _load_cli()
    # docs/archive/** is frozen -- never edited -- so reporting a superseded record's
    # name or shape demands an edit the IA forbids, the mistake _is_frozen_tier undoes
    _seed(tmp_path, "docs/archive/adr/0001-old-decision.md", "# Old decision\n\nsuperseded\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []


# ---- illustrative marker scope ----------------------------------------------


def test_illustrative_marker_quoted_in_a_fence_scopes_to_nothing():
    # references/stamping.md teaches the marker by SHOWING it in a ```markdown fence.
    # A closing fence line is not blank, so the scope walked out of the fence and
    # silenced the prose beneath -- the one page documenting the feature switched the
    # check off for whatever followed it.
    text = (
        "Use it like:\n\n```markdown\n<!-- illustrative -->\n| a |\n```\n"
        "See `gone_a.php:1` and `gone_b.php:2`.\nThere are 42 rules.\n"
    )
    assert [p for _, p, _ in lib.iter_citations(text)] == ["gone_a.php", "gone_b.php"]
    assert [(c[1], c[2]) for c in lib.iter_count_claims(text)] == [("42", "rules")]


def test_illustrative_marker_still_exempts_a_real_mock_table():
    # the fix must not break the case the marker exists for
    mock = (
        "## Final Report\n\n<!-- illustrative -->\n| Thread | Action |\n|---|---|\n"
        "| `file.php:42` | FIXED |\n| `svc.php:15` | 7 files touched |\n\n"
        "Real: `onboard_lib.py:1`\n"
    )
    assert [p for _, p, _ in lib.iter_citations(mock)] == ["onboard_lib.py"]
    assert list(lib.iter_count_claims(mock)) == []


# ---- manager precedence -----------------------------------------------------


def test_js_and_python_manager_come_from_the_root_closest_lockfile(tmp_path, capsys):
    cli = _load_cli()
    # Scanning by lockfile NAME let one legacy nested package-lock.json name the manager
    # for a pnpm monorepo -- reporting `npm`, the very defect the lockfile rule prevents.
    _seed(tmp_path, "package.json", '{"name": "root", "workspaces": ["packages/*"]}')
    _seed(tmp_path, "pnpm-lock.yaml", "lockfileVersion: 9\n")
    _seed(tmp_path, "packages/legacy/package.json", '{"name": "legacy"}')
    _seed(tmp_path, "packages/legacy/package-lock.json", '{"lockfileVersion": 3}')
    # same shape for python: a nested uv.lock must not override the root's requirements
    _seed(tmp_path, "pyproject.toml", '[project]\nname = "x"\nversion = "1"\n')
    _seed(tmp_path, "requirements.txt", "flask==3.0\n")
    _seed(tmp_path, "tools/gen/pyproject.toml", '[project]\nname = "g"\nversion = "1"\n')
    _seed(tmp_path, "tools/gen/uv.lock", "version = 1\n")
    rc = cli.main(["deps-detect", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert next(e for e in out["ecosystems"] if e["name"] == "js")["manager"] == "pnpm"
    assert next(e for e in out["ecosystems"] if e["name"] == "python")["manager"] == "pip"


# ---- LEAKED_PATH: a doc must be able to write the shape down ----------------


def test_leaked_path_exempts_a_placeholder_and_an_illustrative_block(tmp_path, capsys):
    cli = _load_cli()
    # `/Users/...` is the placeholder every doc uses to NAME this forbidden shape, and
    # `.` was in the user-segment character class -- so the page documenting the rule
    # was the one page that could not satisfy it.
    _seed(
        tmp_path,
        "docs/internals/a.md",
        "# A\n\nNo absolute personal path (`/Users/...`) anywhere; write `/home/user` "
        "in examples.\n\n```text illustrative\n/home/someone/proj\n```\n\n"
        "<!-- illustrative -->\n| in | out |\n|---|---|\n| `/Users/someone/x` | `~/x` |\n",
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []
    # a REAL leak in prose is still reported
    _seed(tmp_path, "docs/internals/a.md", "# A\n\nran in /home/mbucko/proj\n")
    rc, codes, lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == ["LEAKED_PATH"]
    assert "/home/mbucko" in lines[0]


# ---- NO_SHOWCASE: what counts as showing ------------------------------------


def test_no_showcase_accepts_a_blockquoted_or_transcript_showcase(tmp_path, capsys):
    cli = _load_cli()
    # `_FENCE_RE` is anchored at ^[ \t]*, so a blockquoted fence is invisible to the
    # grounding machinery -- the page could not be cleared by tagging anything.
    _seed(
        tmp_path,
        "docs/manual/styles.md",
        "# Styles\n\n> All tests pass.\n> ```\n> 638 passed\n> ```\n\n```bash\npytest\n```\n",
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []
    # a shell fence that IS a transcript counts as showing output, tagged or not
    _seed(tmp_path, "docs/manual/styles.md", "# Styles\n\n```console\n$ pytest\n638 passed\n```\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert "NO_SHOWCASE" not in codes
    # a page of bare command lists and nothing else is still reported
    _seed(tmp_path, "docs/manual/styles.md", "# Styles\n\n```bash\npytest\nruff check\n```\n")
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == ["NO_SHOWCASE"]


def test_blockquote_exemption_is_scoped_to_prose_and_a_non_empty_quote(tmp_path, capsys):
    cli = _load_cli()
    # The first cut of the exemption searched the WHOLE file, so a page teaching
    # blockquote syntax inside a fence switched off its own check. (The nested fence is
    # also UNTAGGED_OUTPUT -- incidental to this fixture, so assert on the code under
    # test rather than the whole set.)
    _seed(
        tmp_path,
        "docs/manual/meta.md",
        "# Meta\n\n```bash\nmake up\n```\n\nTo quote a fence, write:\n\n"
        "```markdown\n> ```text\n> output\n> ```\n```\n",
    )
    _rc, codes, _lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert "NO_SHOWCASE" in codes
    # an EMPTY quoted fence shows nothing, so it cannot buy the exemption either
    _seed(
        tmp_path,
        "docs/manual/meta.md",
        "# Meta\n\n```bash\nmake up\n```\n\n> ```text\n> ```\n",
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == ["NO_SHOWCASE"]


# ---- ADR shape reads headings, not substrings -------------------------------


def test_adr_shape_reads_headings_at_any_level_and_ignores_fenced_ones(tmp_path, capsys):
    cli = _load_cli()
    # a bare `"## Context" in text` test answered two ways wrong: `### Context` is the
    # same section at a different depth, and a `## Decision` quoted in a fence is not a
    # section at all
    _seed(
        tmp_path,
        "docs/adr/ADR-0009-x.md",
        "# ADR-0009: X\n\n### Context\nc\n\n### Decision\nd\n\n### Consequences\ne\n",
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []
    # `illustrative` keeps the fence itself out of the grounding checks, so the only
    # finding left is the one under test: the sections are quoted, not present.
    _seed(
        tmp_path,
        "docs/adr/ADR-0009-x.md",
        "# ADR-0009: X\n\n```text illustrative\n## Context\n## Decision\n## Consequences\n```\n",
    )
    rc, codes, lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == ["ADR_SHAPE"]
    assert "## Context" in lines[0]


def test_heading_texts_shares_the_slug_parse():
    # the ADR shape check and the anchor check must agree on what a heading is
    assert lib.heading_texts("# A\n\n## B c\n\n### D\n") == ["A", "B c", "D"]
    assert lib.heading_texts("```\n## Fenced\n```\n\n## Real\n") == ["Real"]
    # a link in a heading contributes its display text, as it does for slugs
    assert lib.heading_texts("## See [docs](x.md)\n") == ["See docs"]


# ---- inline code spans are typeset, not followed -----------------------------


def test_a_link_inside_an_inline_code_span_is_not_a_link(tmp_path, capsys):
    cli = _load_cli()
    # A doc that writes ABOUT a markdown link -- which any page documenting this gate has
    # to -- earned an error-level BROKEN_LINK for a file it never claimed exists. Skipping
    # fences was not enough; a span is typeset, so it names no target.
    _seed(
        tmp_path,
        "docs/a.md",
        "# A\n\nThe heading `### X → [name.md](nonexistent-target.md)` slugs oddly.\n",
    )
    rc, codes, _ = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 0 and codes == []
    # a REAL broken link on the same line as a span is still reported, at the right line
    _seed(
        tmp_path,
        "docs/a.md",
        "# A\n\nreal [gone](nope.md) link, and `[typeset](alsonope.md)` span.\n",
    )
    rc, codes, lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 1 and codes == ["BROKEN_LINK"]
    assert lines[0].endswith("nope.md") and ":3" in lines[0]


def test_code_span_masking_preserves_offsets_and_leaves_non_spans_alone():
    # length-preserving mask => line numbers stay exact
    assert lib.iter_markdown_links("a\n\n`[x](y.md)` [real](r.md)\n") == [("real", "r.md", 3)]
    # an UNCLOSED backtick is not a span, so the link after it is still a link
    assert lib.iter_markdown_links("`unclosed [a](b.md)\n") == [("a", "b.md", 1)]
    # a run that would have to cross a newline is not a span either
    assert lib.iter_markdown_links("`multi\n[a](b.md)line`\n") == [("a", "b.md", 2)]
    # double-backtick spans (which may contain a single backtick) are masked
    assert lib.iter_markdown_links("``a ` [x](y.md)`` [real](r.md)\n") == [("real", "r.md", 1)]


# ---- deny list + operator guidance -----------------------------------------


def test_one_env_glob_covers_the_open_set_of_stage_names():
    """One wildcard, because the enumeration it replaced leaked by construction.

    That list spelled out .env.dev / .env.prod / .env.stage / .env.qa / .env.ci and
    STILL missed .env.uat, .env.preview and .env.e2e -- environment names are an open
    set, so a `deny` assembled from a list is incomplete the moment someone invents a
    name. The four unlisted spellings below are the regression: each was readable.
    """
    perms = lib.plan_project_permissions(["js"])["permissions"]
    assert "Read(**/.env*)" in perms["ask"]
    assert "Edit(**/.env*)" in perms["ask"]

    # fnmatch is a proxy for the real matcher; the gitignore behaviour these assert
    # was verified directly with `git check-ignore` (see ADR-0009).
    for stage in (
        "dev",
        "prod",
        "stage",
        "staging",
        "qa",
        "ci",
        "docker",
        "secret",
        "secrets",
        "local",
        "uat",
        "preview",
        "e2e",
    ):
        assert fnmatch.fnmatch(".env.%s" % stage, ".env*"), stage
    # ...and the bare file the old list needed a second glob (`**/*.env`) to reach
    assert fnmatch.fnmatch(".env", ".env*")

    # The template is knowingly caught, and that is exactly WHY these are `ask`:
    # gitignore patterns carry no negation, so a `deny` wildcard could never spare it.
    assert fnmatch.fnmatch(".env.example", ".env*")
    assert not any(r.startswith(("Read(", "Edit(")) for r in perms["deny"]), (
        "credential globs belong in ask -- a project-level deny silently overrides "
        "the user's own ask, since deny outranks ask across settings scopes"
    )


def test_a_formatter_is_allowed_only_in_its_non_rewriting_form():
    # The update-deps template states the rule for every ecosystem ("use `pint --test`,
    # never `pint`"), but the plan allowed the bare, source-REWRITING command -- which a
    # verify gate could then run unprompted and destroy baseline purity with.
    php = lib.plan_project_permissions(["php"])["permissions"]["allow"]
    assert "Bash(vendor/bin/pint --test)" in php
    assert "Bash(vendor/bin/pint:*)" not in php
    py = lib.plan_project_permissions(["python"])["permissions"]["allow"]
    assert "Bash(ruff format --check)" in py
    assert "Bash(ruff format:*)" not in py
    # the READ-ONLY linters are untouched -- this is about rewriting, not execution
    for rule in ("Bash(ruff check)", "Bash(mypy)", "Bash(pytest)"):
        assert rule in py, rule


def test_captures_not_checked_names_the_invocation_as_the_fix(tmp_path, capsys):
    cli = _load_cli()
    # SKILL.md §3.7 tells the loop to fix every error with a full-file Write. This error
    # is fixable ONLY by adding the flag, so the message has to say so or the loop burns
    # its three rounds rewriting a correct document.
    _seed(tmp_path, "docs/a.md", "# A\n\n```text capture=plan\nout\n```\n")
    rc, codes, lines = _run_check(cli, capsys, [str(tmp_path / "docs")])
    assert rc == 1 and codes == ["CAPTURES_NOT_CHECKED"]
    assert "INVOCATION" in lines[0] and "--captures" in lines[0]


# ---- the template advertises only what it ships ----------------------------


def test_update_deps_template_ships_an_adapter_for_every_advertised_ecosystem():
    # the template advertises its ecosystems in the description/argument-hint, and its
    # own §1 says per-ecosystem mechanics live in the adapter sections -- a repo that
    # stamps it for php or python must find one
    body = (ONBOARD / "templates" / "update-deps" / "SKILL.md").read_text(encoding="utf-8")
    adapters = re.findall(r"(?m)^### (\S+)", body)
    for eco in ("js/ts", "php", "python", "rust", "swift", ".NET"):
        assert eco in adapters, (eco, adapters)
