<!-- markdownlint-disable-file MD014 -->
# Tests

Each plugin has its own checks, run from the folder each section names. CI runs a plugin's checks on a push to `main`
or a pull request that changes its folder or its workflow (batbelt also `tests/**` and `.claude-plugin/**`), or when
started by hand (`workflow_dispatch`); a tag push runs nothing
([ADR-0004](../adr/ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md)). See
`.github/workflows/<plugin>.yml`. Test tools are pinned in the `tests/requirements.txt` of batbelt's and brand-creator's suites (swift's tests use only
the Python standard library). The docs checks are in
the [docs standard, §8](docs-standard.md#8-checks).

## Marketplace

From the repository root:

```bash
$ python3 .github/scripts/check-marketplace.py
```

```console capture=check-marketplace
3 plugins checked, 0 errors
```

The workflow check, which also checks the rulesets, runs from the repository root too. A pass prints
`5 workflows and 4 rulesets checked, 0 errors`, and `--self-test` ends with `self-test: N of N broken rules caught`:

```bash
python3 .github/scripts/check-workflows.py
python3 .github/scripts/check-workflows.py --self-test
```

## batbelt

From the repository root (its tests live in `tests/`). A pass ends with a line like `N passed in Ts`:

```bash
uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q
```

## swift

From `plugins/swift`. A pass ends with `OK`:

```bash
python3 -m unittest discover maintenance/tests
```

CI also runs two checks from `plugins/swift` (`.github/workflows/swift.yml`, steps "Docs gate" and "Instruction
gate"), and validates its manifest ([Manifests](#manifests)). The first checks the docs' links and recorded command
outputs; the second checks that `.claude/rules` and `.claude/skills` cite files and scripts that exist:

```bash
python3 .claude/skills/update-docs/scripts/check.py check-docs docs README.md AGENTS.md --captures docs/.onboard-captures --coverage docs/.onboard-coverage.json
python3 .claude/skills/update-rules/scripts/check.py check-instructions .claude/rules .claude/skills --repo-root .
```

## brand-creator

From `plugins/brand-creator`. Prepare a data directory once (it downloads the Node packages and a headless Chrome),
then run the suite against it:

```bash
bin/brand-creator --data <dir> setup --yes
BRAND_CREATOR_DATA=<dir> tests/run-all.sh --smoke
```

CI runs only quick checks (`.github/workflows/brand-creator.yml`): `claude plugin validate --strict` and the static tests,
about a minute, where any skip fails. Its verdict, the `brand-creator` check, passes only when every job passed. The full
suite runs before each release tag, on a Mac and in the Linux container (`tests/docker/run.sh`)
([ADR-0008](../adr/ADR-0008-ci-runs-quick-checks-the-full-suite-runs-before-a-release.md)). More:
[its development notes](../../plugins/brand-creator/docs/internals/development.md).

Without the data directory, the tests that need it print a "NOT VERIFIED" banner. A skip is not a pass.

## Manifests

These need the Claude Code CLI. In CI, each plugin's workflow runs `claude plugin validate plugins/<name> --strict` and
`marketplace.yml` validates the marketplace file, on the CLI version each workflow pins (`CLAUDE_CODE_VERSION`); a CLI
that cannot be installed fails the job. The release steps validate them again with your own CLI ([Release a plugin](release.md)).

```bash
$ claude plugin validate . --strict
```

```console capture=validate-marketplace
✔ Validation passed
```

`claude plugin validate plugins/<name> --strict` checks one plugin the same way.
