# Work on the plugin

On a clean tree, the three free checks print this:

```text capture=check-apis-strict
111 manifest APIs, 0 failures, 0 warnings
```

```text capture=unit-tests
Ran 130 tests in 2.419s

OK
```

```text capture=validate-plugin
✔ Validation passed
```

Those come from `python3 maintenance/check-apis.py --strict`, `python3 -m unittest discover maintenance/tests` and `claude plugin validate plugins/swift`. Run every command on this page from the repo root.

## Try a change

Load the plugin from the checkout instead of an install:

```bash
claude --plugin-dir plugins/swift
```

Edits show up in the next session started this way. Installed copies don't change until a release.

## Check every API name against Apple

```bash
python3 maintenance/check-apis.py --strict
```

It resolves every API-shaped name in `plugins/swift/skills/**/*.md` against Apple's documentation indexes, and checks each recorded claim in `maintenance/apis.json` (for example "not on visionOS") against Apple's platform data. Without `--strict`, unresolved names are warnings; with it, they fail. Flags, exit codes and the manifest format: [check-apis reference](reference/check-apis.md).

The platform table in `plugins/swift/skills/swiftui/references/platform-availability.md` is generated. Its rows are the `apis.json` entries with `"table": true`, and its cells come from Apple's data for each entry's `path`; claims never reach it. Regenerate it after adding or removing a `"table": true` entry, changing one's `name` or `path`, or refreshing Apple's data with `--refresh`:

```bash
python3 maintenance/check-apis.py --write-table
```

It refuses to write while any manifest check fails (`run` in `maintenance/apicheck/cli.py`).

## Run the unit tests

```bash
python3 -m unittest discover maintenance/tests
```

## Validate the manifests

```bash
claude plugin validate .
claude plugin validate plugins/swift
```

Both pass with no warnings. The marketplace check reads:

```text capture=validate-marketplace
✔ Validation passed
```

## Run the evals

Every eval run spends model calls, so always pass a cost ceiling, and pass `--no-publish` to keep the HTML report local; without it the report is published (`claude plugin eval --help`):

```bash
claude plugin eval plugins/swift --scaffold --trust-plugin --no-publish --max-cost-usd 30 --allow-tools Write Edit
```

That runs every case three times with the plugin and three times without it (`--ablation with-without` is the default when a plugin is the target), and the report compares the two. To check one case once, with the plugin only, run:

```bash
claude plugin eval plugins/swift --scaffold --trust-plugin --no-publish --runs 1 --ablation none --case preview-debug-guard --max-cost-usd 30 --allow-tools Write Edit
```

which prints a summary like this one:

```text capture=eval-one-case
CASE                 SCORE PASS% RUNS COST    NOTES
preview-debug-guard  1.00  100%  1    $0.15
```

Results go to `plugins/swift/evals/results/`, which is gitignored.

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

Every change under a forked skill's folder (`plugins/swift/skills/swiftui/`, `plugins/swift/skills/concurrency/`, `plugins/swift/skills/testing/`) is its own commit, with a row in that upstream's `UPSTREAM.md` section → Deviations in the same commit. `git diff <local-import-tag> -- <skill-folder>` then shows exactly what differs from upstream.

## Release

Versions follow SemVer, and `version` in `plugins/swift/.claude-plugin/plugin.json` is the only place the version lives ([ADR-0003](../adr/ADR-0003-explicit-semver-one-version-home.md)). Before 1.0, a breaking change bumps the minor version (0.2.0 renamed the marketplace), and a feature or fix bumps the patch. Each release gets the tag `swift--v<version>`, created by `claude plugin tag`.

Prerequisite: the `origin` remote points at `jack1913/swift-plugin`.

1. Run the `changelog-release` skill. It raises `version` in `plugins/swift/.claude-plugin/plugin.json`, writes `CHANGELOG.md` and stages both; it never commits (`.claude/skills/changelog-release/SKILL.md`).
2. Commit.
3. Check the tag with a dry run, then create it:

   ```bash
   claude plugin tag plugins/swift --dry-run
   claude plugin tag plugins/swift
   ```

For release 0.1.5, the dry run read:

```text capture=tag-dry-run
Version: 0.2.1 (from plugin.json)
Tag:     swift--v0.2.1
```

4. Push the commit, then the tag:

   ```bash
   git push origin main
   git push origin swift--v<version>
   ```

A push without a version bump never reaches installs, because Claude Code keys updates on the version ([Plugins reference: version management](https://code.claude.com/docs/en/plugins-reference)).
