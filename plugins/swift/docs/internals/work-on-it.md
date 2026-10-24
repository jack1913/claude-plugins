# Work on the plugin

On a clean tree, the three free checks print this:

```text capture=check-apis-strict
111 manifest APIs, 0 failures, 0 warnings
```

```text capture=unit-tests
Ran 130 tests in 2.557s

OK
```

```text capture=validate-plugin
✔ Validation passed
```

They come from `python3 maintenance/check-apis.py --strict`, `python3 -m unittest discover maintenance/tests` and `claude plugin validate .`. Run every command on this page from the plugin folder (`plugins/swift/` in the `jack1913/claude-plugins` checkout), except `claude plugin tag`, which runs from the monorepo root.

## Try a change

Load the plugin from the checkout instead of an install:

```bash
claude --plugin-dir .
```

Edits show up in the next session started this way. Installed copies don't change until a release.

## Check every API name against Apple

```bash
python3 maintenance/check-apis.py --strict
```

It resolves every API-shaped name in `skills/**/*.md` against Apple's documentation indexes, and checks each recorded claim in `maintenance/apis.json` (for example "not on visionOS") against Apple's platform data. Without `--strict`, unresolved names are warnings; with it, they fail. Flags, exit codes and the manifest format: [check-apis reference](check-apis.md).

The platform table in `skills/swiftui/references/platform-availability.md` is generated. Its rows are the `apis.json` entries with `"table": true`, and its cells come from Apple's data for each entry's `path`; claims never reach it. Regenerate it after adding or removing a `"table": true` entry, changing one's `name` or `path`, or refreshing Apple's data with `--refresh`:

```bash
python3 maintenance/check-apis.py --write-table
```

It refuses to write while any manifest check fails (`run` in `maintenance/apicheck/cli.py`).

## Run the unit tests

```bash
python3 -m unittest discover maintenance/tests
```

## Validate the manifest

```bash
claude plugin validate .
```

It passes with no warnings. The marketplace manifest is the monorepo's `.claude-plugin/marketplace.json`; validate it from the monorepo root with `claude plugin validate . --strict`.

## Run the evals

Every eval run spends model calls, so always pass a cost ceiling, and pass `--no-publish` to keep the HTML report local; without it the report is published (`claude plugin eval --help`):

```bash
claude plugin eval . --scaffold --trust-plugin --no-publish --max-cost-usd 30 --allow-tools Write Edit
```

That runs every case three times with the plugin and three times without it (`--ablation with-without` is the default when a plugin is the target), and the report compares the two. To check one case once, with the plugin only, run:

```bash
claude plugin eval . --scaffold --trust-plugin --no-publish --runs 1 --ablation none --case preview-debug-guard --max-cost-usd 30 --allow-tools Write Edit
```

which prints a summary like this one:

```text capture=eval-one-case
CASE                 SCORE PASS% RUNS COST    NOTES
preview-debug-guard  1.00  100%  1    $0.15
```

Results go to `evals/results/`, which is gitignored.

## Check upstream for changes

```bash
maintenance/upstream-diff.sh <swiftui|concurrency|testing> [ref]
```

The first argument picks the upstream; with no `ref` it compares against that upstream's newest plain `X.Y.Z` tag (a leading `v` is allowed; pre-release tags are skipped):

```text capture=upstream-diff
upstream: https://github.com/AvdLee/SwiftUI-Agent-Skill (skills/swiftui-expert-skill)
baseline: 5.1.0 -> ref: 5.1.0
no upstream changes: 5.1.0 is the baseline
```

That is `maintenance/upstream-diff.sh swiftui`. It clones the upstream into a temp dir and diffs its skill folder between the baseline in that upstream's `UPSTREAM.md` section and the ref; it never writes to this repo. Port changes by hand, then update the section's baseline and Ported table.

## Change a forked skill

Every change under a forked skill's folder (`skills/swiftui/`, `skills/concurrency/`, `skills/testing/`) is its own commit, with a row in that upstream's `UPSTREAM.md` section → Deviations in the same commit. `git diff <local-import-tag> -- <skill-folder>` then shows exactly what differs from upstream.

## Release

Versions follow SemVer, and `version` in `.claude-plugin/plugin.json` is the only place the version lives ([ADR-0003](../adr/ADR-0003-explicit-semver-one-version-home.md)). Before 1.0, a breaking change bumps the minor version (0.2.0 and 0.3.0 changed the marketplace and so the install ID), and a feature or fix bumps the patch. Each release gets the tag `swift--v<version>`, created by `claude plugin tag`.

Prerequisite: the `origin` remote of the monorepo checkout points at `jack1913/claude-plugins`, which holds the plugin and the marketplace `jack1913` ([ADR-0015](../adr/ADR-0015-plugin-moves-into-the-claude-plugins-monorepo.md)). The marketplace entry for `swift` carries no `version`, so a release needs no change there.

1. Run the `changelog-release` skill. It raises `version` in `.claude-plugin/plugin.json`, writes `CHANGELOG.md` and stages both; it never commits (`.claude/skills/changelog-release/SKILL.md`).
2. Commit, and push the commit alone:

   ```bash
   git push origin main
   ```

3. Wait until every CI run of that commit has passed. In the monorepo a tag push runs no CI, so this run is the release's only check:

   ```bash
   gh run list --commit "$(git rev-parse HEAD)" --json workflowName,status,conclusion
   ```

   The list must name at least `docs` and `swift` (a release commit changes `CHANGELOG.md` and `plugin.json`), every run with `"status":"completed"` and `"conclusion":"success"`. An empty list means the runs have not started yet: ask again in a minute. If one fails, fix it in a new commit first.

4. From the monorepo root, check the tag with a dry run, then create it and push it:

   ```bash
   claude plugin tag plugins/swift --dry-run
   claude plugin tag plugins/swift
   git push origin swift--v<version>
   ```

   The dry run prints the plugin name, the version it read from `plugin.json`, and the tag it would create (`swift--v<version>`), then the `git tag` and `git push` commands it would run. It creates nothing.

A push without a version bump never reaches installs, because Claude Code keys updates on the version ([Plugins reference: version management](https://code.claude.com/docs/en/plugins-reference)).
