# Repository layout

`.claude-plugin/` and `.github/` are the marketplace itself: one `marketplace.json`, helper scripts, and one workflow per
plugin plus `marketplace.yml` and `docs.yml`, one release-tag ruleset per plugin and one ruleset for `main`. Why one repository:
[ADR-0001](../adr/ADR-0001-one-monorepo-marketplace.md).

| Path | What it holds |
| --- | --- |
| `.claude-plugin/marketplace.json` | The marketplace `jack1913`; every `source` is `./plugins/<name>` |
| `.github/workflows/<plugin>.yml` | That plugin's CI, run on a push to `main` or a pull request that changes its folder or its workflow file (batbelt: also `tests/**` and `.claude-plugin/**`), or by hand; never on a tag |
| `.github/workflows/marketplace.yml` | Checks `marketplace.json` (also with `claude plugin validate`), the shape of every workflow and the rulesets |
| `.github/workflows/docs.yml` | Checks the docs against the [docs standard](docs-standard.md), and runs the workflow check, because every release-tag ruleset requires its job |
| `.github/scripts/` | The checks those two workflows run: `check-marketplace.py`, `check-workflows.py`, `check-docs-standard.py` |
| `.github/rulesets/main-branch.json` | The branch ruleset of `main` on GitHub: never deleted, never force-pushed ([ADR-0006](../adr/ADR-0006-main-and-release-tags-cannot-be-rewritten.md)) |
| `.github/rulesets/<plugin>-release-tags.json` | The tag ruleset that plugin's releases need on GitHub: a tag `<plugin>--v*` only on a commit where the checks `<plugin>` and `docs` passed, never deleted or moved once pushed ([Release a plugin](release.md#the-tag-rulesets)) |
| `plugins/<name>/` | One plugin: `.claude-plugin/plugin.json`, docs, tests, `CHANGELOG.md`, version (batbelt: its tests are in the root `tests/`) |
| `tests/` | batbelt's tests (brand-creator and swift keep theirs in their own folder) |
| `docs/` | The marketplace's manual, internals and decision records |

Each folder under `plugins/` is self-contained (except batbelt's tests), versioned on its own, and tagged per release
as `<plugin>--vX.Y.Z` ([ADR-0002](../adr/ADR-0002-per-plugin-versions-and-tags.md); `git tag -l '<plugin>--v*'` lists
a plugin's tags). A plugin's own `AGENTS.md`, `CLAUDE.md` or `README.md` has the rules for working on it.

To see which plugins the marketplace lists: `jq -r '.plugins[].name' .claude-plugin/marketplace.json`.
