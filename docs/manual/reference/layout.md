<!-- markdownlint-disable-file MD014 -->
# Repository layout

`.claude-plugin/` and `.github/` are the marketplace itself: one `marketplace.json`, one check, one workflow per plugin
plus `marketplace.yml`.

```bash
$ git ls-files .claude-plugin .github
```

```console capture=layout-files
.claude-plugin/marketplace.json
.github/scripts/check-marketplace.py
.github/workflows/batbelt.yml
.github/workflows/brand-creator.yml
.github/workflows/marketplace.yml
.github/workflows/swift.yml
```

The plugins `marketplace.json` lists, and where each one lives:

```bash
$ jq -r '.plugins[] | "\(.name)  \(.source)"' .claude-plugin/marketplace.json
```

```console capture=marketplace-plugins
brand-creator  ./plugins/brand-creator
swift  ./plugins/swift
batbelt  ./plugins/batbelt
```

The rest of the tree (the root [`README.md`](../../../README.md), "Layout";
[ADR-0001](../../adr/ADR-0001-one-monorepo-marketplace.md)):

| Path | What it holds |
| --- | --- |
| `.claude-plugin/marketplace.json` | The marketplace `jack1913`; every `source` is `./plugins/<name>` |
| `.github/workflows/<plugin>.yml` | That plugin's CI, run when its folder or its workflow file changes (batbelt: also `tests/**` and `.claude-plugin/**`) or by hand |
| `.github/workflows/marketplace.yml` | Checks `marketplace.json` |
| `.github/scripts/check-marketplace.py` | The `marketplace.json` check that `marketplace.yml` runs |
| `plugins/<name>/` | One plugin: `.claude-plugin/plugin.json`, docs, tests, `CHANGELOG.md`, version (batbelt: no `CHANGELOG.md` yet, and its tests are in the root `tests/`) |
| `tests/` | batbelt's tests (brand-creator and swift keep theirs in their own folder) |
| `docs/` | This manual, internals, and the marketplace's decision records |

Each folder under `plugins/` is self-contained (except batbelt's tests), versioned on its own, and tagged per release
as `<plugin>--vX.Y.Z` ([ADR-0002](../../adr/ADR-0002-per-plugin-versions-and-tags.md); only swift has tags so far).
A plugin's own `AGENTS.md`, `CLAUDE.md` or `README.md` has the rules for working on it.
