# Work on the plugin

On a clean tree, the three free checks print this:

```text capture=check-apis-strict
111 manifest APIs, 0 failures, 0 warnings
```

```text capture=unit-tests
Ran 96 tests in 0.060s

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

The marketplace check passes with one warning, which is expected (the marketplace has no top-level description):

```text capture=validate-marketplace
⚠ Found 1 warning:

  ❯ description: No marketplace description provided. Adding a description helps users understand what this marketplace offers

✔ Validation passed with warnings
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
maintenance/upstream-diff.sh [ref]
```

With no `ref` it compares against upstream's newest plain `X.Y.Z` tag (a leading `v` is allowed; pre-release tags are skipped):

```text capture=upstream-diff
upstream: https://github.com/AvdLee/SwiftUI-Agent-Skill (skills/swiftui-expert-skill)
baseline: 5.1.0 -> ref: 5.1.0
no upstream changes: 5.1.0 is the baseline
```

It clones upstream into a temp dir and diffs `skills/swiftui-expert-skill/` between the baseline in `UPSTREAM.md` and the ref; it never writes to this repo. Port changes by hand, then update the baseline and the Ported table in `UPSTREAM.md`.

## Change `swift:swiftui`

Every change under `plugins/swift/skills/swiftui/` is its own commit, with a row in `UPSTREAM.md` → Deviations in the same commit. `git diff upstream-5.1.0 -- plugins/swift/skills/swiftui` then shows exactly what differs from upstream.

## Release

Prerequisite: the `origin` remote points at `jack1913/swift-plugin`.

1. Run the `changelog-release` skill. It raises `version` in `plugins/swift/.claude-plugin/plugin.json`, writes `CHANGELOG.md` and stages both; it never commits (`.claude/skills/changelog-release/SKILL.md`).
2. Commit.
3. Check the tag with a dry run, then create it:

   ```bash
   claude plugin tag plugins/swift --dry-run
   claude plugin tag plugins/swift
   ```

For release 0.1.3, the dry run read:

```text capture=tag-dry-run
Version: 0.1.3 (from plugin.json)
Tag:     swift--v0.1.3
```

4. Push the commit, then the tag:

   ```bash
   git push origin main
   git push origin swift--v<version>
   ```

A push without a version bump never reaches installs, because Claude Code keys updates on the version ([Plugins reference: version management](https://code.claude.com/docs/en/plugins-reference)).
