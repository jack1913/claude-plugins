<!-- markdownlint-disable-file MD014 -->
# Add a plugin

A new plugin is a folder, a marketplace entry, a workflow and a release-tag ruleset. Three checks confirm the result before you push (step 4).
Cutting its first release is on [Release a plugin](release.md).

## 1. Create the folder

Create `plugins/<name>/` with `.claude-plugin/plugin.json` (its `name` equal to the folder name, and its `version`, the
only place the version lives), its docs and its tests. Docs follow the [docs standard](docs-standard.md).

## 2. List it in the marketplace

Add an entry to `.claude-plugin/marketplace.json` with `"source": "./plugins/<name>"`, a `name`, a `category` and
`tags`, and no `version`. `check-marketplace.py` fails when two entries share a name, when a source is not
`./plugins/<name>`, when the folder or its `plugin.json` is missing or names a different plugin, or when a folder under
`plugins/` is not listed (the full list is the docstring at the top of `.github/scripts/check-marketplace.py`).

## 3. Add its workflow

Add `.github/workflows/<name>.yml` that runs the plugin's tests, triggered on `push` to `main` only (so a tag push runs
nothing), `pull_request` and `workflow_dispatch`, with the same `paths:` filter on both (`plugins/<name>/**` and the
workflow file), a pinned runner image such as `ubuntu-24.04`, `timeout-minutes` on every job, `permissions: contents: read`
and a `claude plugin validate --strict` step for the plugin on the pinned CLI (`CLAUDE_CODE_VERSION`). Name its job `<name>`:
that job is the workflow's verdict, the check its release tags need. A workflow of several jobs adds that job last; it
needs every other job, runs `if: ${{ always() }}` and copies its steps word for word from
`.github/workflows/brand-creator.yml`, where they fail unless every job it needs succeeded. Copy an existing
workflow, for example `.github/workflows/swift.yml`. The rule is in `.claude/rules/ci-workflow-per-plugin.md`, and
`.github/scripts/check-workflows.py` checks it.

Then write the plugin's release-tag ruleset and create it on GitHub, from the repository root:

```bash
python3 .github/scripts/check-workflows.py --ruleset <name> > .github/rulesets/<name>-release-tags.json
gh api --method POST 'repos/{owner}/{repo}/rulesets' --input .github/rulesets/<name>-release-tags.json
```

Until the ruleset exists on GitHub, the plugin's tags are not checked ([The tag rulesets](release.md#the-tag-rulesets)).

## 4. Check, then push

```bash
$ python3 .github/scripts/check-marketplace.py
$ python3 .github/scripts/check-workflows.py
$ claude plugin validate . --strict
$ claude plugin validate plugins/<name> --strict
```

The marketplace check prints one summary line:

```console capture=check-marketplace
3 plugins checked, 0 errors
```

Each validate command ends with:

```console capture=validate-batbelt
✔ Validation passed
```

Then run the docs checks ([docs standard, §8](docs-standard.md#8-checks)), commit and push.

## 5. Release it

Releases are tagged per plugin from the repository root. See [Release a plugin](release.md).
