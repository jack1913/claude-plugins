<!-- markdownlint-disable-file MD014 -->
# Tests

Each plugin has its own checks, run from the folder each section names. CI runs a plugin's checks when its folder or
its workflow changes (batbelt also on `tests/**` and `.claude-plugin/**`), or when started by hand
(`workflow_dispatch`); see `.github/workflows/<plugin>.yml`.

## Marketplace

From the repository root:

```bash
$ python3 .github/scripts/check-marketplace.py
```

```console capture=check-marketplace
3 plugins checked, 0 errors
```

## batbelt

From the repository root (its tests live in `tests/`):

```bash
$ uv run --no-project --with pytest --with pyyaml python -m pytest tests -q
```

```console capture=batbelt-tests
393 passed in 2.43s
```

## swift

From `plugins/swift`:

```bash
$ python3 -m unittest discover maintenance/tests
```

```console capture=swift-tests
Ran 130 tests in 5.754s

OK
```

CI also runs two checks from `plugins/swift` (`.github/workflows/swift.yml`, steps "Docs gate" and "Instruction
gate"). The first checks the docs' links and recorded command outputs; the second checks that `.claude/rules` and
`.claude/skills` cite files and scripts that exist:

```bash
python3 .claude/skills/update-docs/scripts/check.py check-docs docs README.md AGENTS.md --captures docs/.onboard-captures --coverage docs/.onboard-coverage.json
python3 .claude/skills/update-rules/scripts/check.py check-instructions .claude/rules .claude/skills --repo-root .
```

## brand-creator

From `plugins/brand-creator`. Prepare a data directory once (it downloads the Node packages and a headless Chrome),
then run the suite against it. Not captured here: it needs that data directory.

```bash
bin/brand-creator --data <dir> setup --yes
BRAND_CREATOR_DATA=<dir> tests/run-all.sh --smoke
```

CI runs the same suite inside a Linux container (`tests/docker/run.sh`) and the Apple-tool tests on macOS
(`.github/workflows/brand-creator.yml`). More: [its README, "Development"](../../../plugins/brand-creator/README.md#development).

Without the data directory, the tests that need it print a "NOT VERIFIED" banner. A skip is not a pass.

## Manifests

These need the Claude Code CLI. CI runs it only in `brand-creator.yml`, for brand-creator, when the CLI is available;
no workflow runs `claude plugin validate .`.

```bash
$ claude plugin validate . --strict
```

```console capture=validate-marketplace
✔ Validation passed
```

`claude plugin validate plugins/<name> --strict` checks one plugin the same way.
