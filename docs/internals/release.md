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
   check ([ADR-0004](../adr/ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md)), and GitHub accepts the tag
   only on a commit where the checks `<name>` and `docs` passed (the tag rulesets below):

   ```bash
   gh run list --commit "$(git rev-parse HEAD)" --json workflowName,status,conclusion
   ```

   The list must name at least `docs` and the plugin's own workflow (a release commit changes `CHANGELOG.md` and
   `plugin.json`), every run with `"status":"completed"` and `"conclusion":"success"`. An empty list means the runs
   have not started yet: ask again in a minute. If one fails, fix it in a new commit and wait again; never tag a commit
   whose CI failed. The tag then goes on the fix commit, which needs both checks too: a workflow whose paths that commit
   did not change never starts there, so start it by hand on `main`'s current commit with
   `gh workflow run <workflow>.yml --ref main` (`docs.yml`, or the plugin's own).
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

   Pushed too early, the tag is refused, and nothing is created on GitHub:

   ```text illustrative
   remote: error: GH013: Repository rule violations found for refs/tags/<name>--vX.Y.Z.
   remote: - Required status check "<name>" is expected.
    ! [remote rejected] <name>--vX.Y.Z -> <name>--vX.Y.Z (push declined due to repository rule violations)
   ```

   "is expected" means the check has no result on that commit: its workflow is still running (wait, then push the tag
   again), or it never started there (start it by hand, as in step 4). "is failing" means it failed: fix it in a new
   commit, delete the local tag (`git tag -d <name>--vX.Y.Z`), and tag the new commit once both checks passed on it.

Use `claude plugin tag`, never `git tag`. It reads the version from `plugin.json`, checks it against the marketplace
entry, and names the tag `<name>--vX.Y.Z` for you.

## The tag rulesets

Each plugin has a tag ruleset on GitHub, "<name> release tags" (Settings, Rules, Rulesets): a tag `<name>--v*` is accepted
only on a commit where the checks `<name>` and `docs` passed, and once pushed it can be neither deleted nor moved. Each
check is its workflow's verdict, a job named after the workflow that passes only when every other job in it passed. Nobody
can bypass the rulesets. Why: [ADR-0005](../adr/ADR-0005-release-tags-need-a-passing-ci-verdict.md) and
[ADR-0006](../adr/ADR-0006-main-and-release-tags-cannot-be-rewritten.md).

A tag pushed by mistake therefore stays. To remove or move one, set its ruleset's enforcement to Disabled, change the tag,
then set it back to Active and confirm with `--live`. `main` has a ruleset of its own, "main branch": it can be neither
deleted nor force-pushed, and a push that only adds commits goes through.

Their source is `.github/rulesets/<name>-release-tags.json`, and `main-branch.json` for `main`, which `check-workflows.py`
checks in CI. GitHub keeps its own copy, so after changing a file, or to catch a change made in the web interface, compare
the two from the repository root (it needs `gh`, signed in):

```bash
python3 .github/scripts/check-workflows.py --live
```

It also reports a ruleset on GitHub that no file describes, which could refuse tags or pushes on its own. A difference is
printed with the `gh api` command that brings GitHub's copy in line with the file.

## Installed copies update only on a bump

Claude Code reads the version from `plugin.json`. A push that does not bump it never reaches installed copies. Users
then update with `claude plugin update <name>@jack1913` (see [Install a plugin](../manual/getting-started/install-a-plugin.md)).

## Tag an earlier release

`claude plugin tag` tags `HEAD`. A release that was never tagged can be tagged later only from a checkout of its own
commit: check it out, then run the same command there. List what is tagged with `git tag -l '<name>--v*'`.

A commit made before the verdict jobs existed (ADR-0005) has no `<name>` check, so its ruleset refuses the tag. Set that ruleset's enforcement to
Disabled (Settings, Rules, Rulesets), push the tag, then set it back to Active and confirm with `--live`.
