<!-- markdownlint-disable-file MD014 -->
# Add a plugin

A new plugin is a folder, a marketplace entry and a workflow. Two checks confirm the result before you push (step 4),
and a dry run shows the release tag before it exists (step 5).

## 1. Create the folder

Create `plugins/<name>/` with `.claude-plugin/plugin.json` (its `name` equal to the folder name, and its `version`, the
only place the version lives), its docs and its tests.

## 2. List it in the marketplace

Add an entry to `.claude-plugin/marketplace.json` with `"source": "./plugins/<name>"`, a `name` and a `description`,
and no `version`. `check-marketplace.py` fails when two entries share a name, when a source is not `./plugins/<name>`,
when the folder or its `plugin.json` is missing or names a different plugin, or when a folder under `plugins/` is not
listed (the full list is the docstring at the top of `.github/scripts/check-marketplace.py`).

## 3. Add its workflow

Add `.github/workflows/<name>.yml` that runs the plugin's tests, triggered on `push`, `pull_request` and
`workflow_dispatch`, with the same `paths:` filter on both (`plugins/<name>/**` and the workflow file) and
`permissions: contents: read`. Copy an existing one, for example `.github/workflows/swift.yml`.

## 4. Check, then push

```bash
$ python3 .github/scripts/check-marketplace.py
$ claude plugin validate . --strict
$ claude plugin validate plugins/<name> --strict
```

The marketplace check, on today's three plugins:

```console capture=check-marketplace
3 plugins checked, 0 errors
```

For batbelt, the last command ends with:

```console capture=validate-batbelt
✔ Validation passed
```

## 5. Tag a release

Tag from the repository root with `claude plugin tag`, not `git tag`: it reads the version from `plugin.json`, checks
the marketplace entry first, and names the tag `<plugin>--vX.Y.Z` for you. Dry run for batbelt:

```bash
$ claude plugin tag plugins/batbelt --dry-run
```

```console capture=tag-dry-run
Plugin:  batbelt
Version: 0.1.1 (from plugin.json)
Marketplace entry: plugins[2] in ~/Dev/claude_skills/claude-plugins/.claude-plugin/marketplace.json
Tag:     batbelt--v0.1.1

✔ Dry run — would create tag batbelt--v0.1.1 at HEAD in ~/Dev/claude_skills/claude-plugins
  git -C ~/Dev/claude_skills/claude-plugins tag -a batbelt--v0.1.1 -m "batbelt 0.1.1"
  git -C ~/Dev/claude_skills/claude-plugins push origin refs/tags/batbelt--v0.1.1
```

Read the printed git commands before running it without `--dry-run`: the tag lands on `HEAD`. Why versions and tags
work this way: [ADR-0002](../../adr/ADR-0002-per-plugin-versions-and-tags.md).
