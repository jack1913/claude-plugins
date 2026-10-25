# ADR-0006: `main` and release tags cannot be rewritten

- **Status:** accepted
- **Date:** 2026-10-25
- **Source:** GitHub's "Available rules for rulesets" (restrict deletions, restrict updates, block force pushes) and the REST
  schema of a ruleset's rules, where creating, updating and deleting a matching ref are three separate rules;
  this repository's rulesets as read on 2026-10-25; `.github/scripts/check-workflows.py`

## Context

The marketplace installs every plugin from `main`, and a release tag records that its commit passed CI
([ADR-0005](ADR-0005-release-tags-need-a-passing-ci-verdict.md)). The tag rulesets required passing checks on a tag's
commit, but did not forbid deleting a release tag or moving it to another commit whose checks passed. `main` had no
ruleset, so one mistaken `git push --force` would have rewritten what every install pulls.

## Decision

- Each release-tag ruleset also restricts updates and deletions: once pushed, a tag `<plugin>--v*` can be neither moved
  nor deleted. Creating a tag is a separate rule that stays unrestricted, so a new release tag still needs only its checks.
- A branch ruleset, "main branch", restricts deleting `main` and blocks force pushes to it. It requires nothing else, so a
  push that only adds commits goes through, as the direct pushes of
  [ADR-0004](ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md) need. Nobody can bypass it.
- Its source is `.github/rulesets/main-branch.json`, next to the tag rulesets: `check-workflows.py` checks the file and
  prints it (`--ruleset main`), and `--live` compares it with GitHub, as it does the tag rulesets.

Rejected:

- Required status checks or pull requests on `main`: releases land by direct pushes (ADR-0004), and the run on `main` is
  the commit's verdict.
- A bypass for repository admins: the only person who pushes is an admin, so the rules would never apply.

## Consequences

- A release tag pushed by mistake stays. Removing or moving it means setting its ruleset to Disabled for that one push, as
  tagging an earlier release already does ([Release a plugin](../internals/release.md)).
- Rewriting `main` on purpose, for example to purge a leaked key from its history, means setting "main branch" to Disabled
  first, then back to Active and confirming with `check-workflows.py --live`.
- `.github/rulesets/` now holds a ruleset that requires no check: only the release-tag rulesets require `docs`.
