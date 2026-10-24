# Release a plugin

A release is a version in the plugin's `plugin.json`, a dated section in its `CHANGELOG.md`, and a git tag
`<name>--vX.Y.Z`. Each plugin releases on its own; there is no repo-wide version.
Why: [ADR-0002](../adr/ADR-0002-per-plugin-versions-and-tags.md).

## Cut a release

1. Run the `changelog-release` skill for that one plugin. It writes the dated `CHANGELOG.md` section from
   `[Unreleased]` and bumps `version` in `plugins/<name>/.claude-plugin/plugin.json`, then stages the changes. It never
   commits. (swift has its own copy, `plugins/swift/.claude/skills/changelog-release`; the root skill hands swift to it.)
2. Validate the manifests, from the repository root:

   ```bash
   claude plugin validate . --strict
   claude plugin validate plugins/<name> --strict
   ```

3. Commit and push the changelog and version bump.
4. Wait until every CI run of that commit on `main` has passed. A tag push runs no CI, so this run is the release's only
   check ([ADR-0004](../adr/ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md)):

   ```bash
   gh run list --commit "$(git rev-parse HEAD)" --json workflowName,status,conclusion
   ```

   The list must name at least `docs` and the plugin's own workflow (a release commit changes `CHANGELOG.md` and
   `plugin.json`), every run with `"status":"completed"` and `"conclusion":"success"`. An empty list means the runs
   have not started yet: ask again in a minute. If one fails, fix it in a new commit and wait again; never tag a commit
   whose CI failed.
5. Dry-run the tag, from the repository root:

   ```bash
   claude plugin tag plugins/<name> --dry-run
   ```

   It prints the plugin, the version it read from `plugin.json`, the tag name and the `git` commands it would run.
   Check that the version and the tag name are the ones you meant.
6. Run it again without `--dry-run`. The tag lands on `HEAD`. It is created only in your clone: the command prints
   the push line instead of running it.
7. Push the tag:

   ```bash
   git push origin refs/tags/<name>--vX.Y.Z
   ```

Use `claude plugin tag`, never `git tag`. It reads the version from `plugin.json`, checks it against the marketplace
entry, and names the tag `<name>--vX.Y.Z` for you.

## Installed copies update only on a bump

Claude Code reads the version from `plugin.json`. A push that does not bump it never reaches installed copies. Users
then update with `claude plugin update <name>@jack1913` (see [Install a plugin](../manual/getting-started/install-a-plugin.md)).

## Tag an earlier release

`claude plugin tag` tags `HEAD`. A release that was never tagged can be tagged later only from a checkout of its own
commit: check it out, then run the same command there. List what is tagged with `git tag -l '<name>--v*'`.
