<!-- markdownlint-disable-file MD014 -->
# Add a plugin

A new plugin is a folder, a marketplace entry and a workflow. Two checks confirm the result before you push (step 4).
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

Add `.github/workflows/<name>.yml` that runs the plugin's tests, triggered on `push`, `pull_request` and
`workflow_dispatch`, with the same `paths:` filter on both (`plugins/<name>/**` and the workflow file) and
`permissions: contents: read`. Copy an existing one, for example `.github/workflows/swift.yml`. The rule is in
`.claude/rules/ci-workflow-per-plugin.md`.

## 4. Check, then push

```bash
$ python3 .github/scripts/check-marketplace.py
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
