# ADR-0005: A release tag is accepted only on a commit whose CI passed

- **Status:** accepted
- **Date:** 2026-10-25
- **Source:** GitHub's "Available rules for rulesets" (required status checks apply to a branch or tag) and the REST schema of
  the `required_status_checks` rule; GitHub Actions' `jobs.<job_id>.if` (a skipped job reports success); this repository's
  check runs from 2026-10-19 to 2026-10-25; a temporary tag ruleset tested on 2026-10-25; `.github/scripts/check-workflows.py`

## Context

[ADR-0004](ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md) made a release a manual sequence: push the release
commit, wait until every CI run of it has passed, then push the tag. Nothing enforced the wait, and before ADR-0004
`brand-creator--v0.3.5` had been tagged on a commit whose CI on `main` failed.

A GitHub tag ruleset with required status checks rejects a push that creates or moves a matching tag unless the named checks
passed on the commit the tag points to. A temporary ruleset tested on this repository with annotated tags, the kind
`claude plugin tag` makes, accepted a tag on a commit whose required check had passed, and rejected one on a commit with no
such check ("Required status check "linux" is expected") and one on a commit where it failed ("... is failing").

A required check is matched by its name, and the workflows' names collided: batbelt's and swift's jobs were both `test`,
docs' and marketplace's both `check`, so a commit that started both reported two checks of each name. brand-creator's
result was spread over six checks.

## Decision

- Every workflow has one job named after it, its verdict, with no condition of its own (a job that is skipped reports
  success). In a workflow of several jobs it needs every other job, runs `if: ${{ always() }}`, so a failure cannot skip
  it, and its steps fail unless every job it needs succeeded. No other job's check carries a workflow's name. A job that
  cannot do its work fails instead of passing: brand-creator's `validate` fails when the Claude Code CLI cannot be
  installed.
- Each plugin has a tag ruleset, "<plugin> release tags": a tag matching `refs/tags/<plugin>--v*` is accepted only on a
  commit where the checks `<plugin>` and `docs` passed, both from GitHub Actions. Every release commit starts both
  workflows: it changes the plugin's `CHANGELOG.md` and `plugin.json`. The ruleset is enforced on creation, and nobody can
  bypass it.
- The rulesets' source is `.github/rulesets/<plugin>-release-tags.json`, the body of GitHub's create-ruleset request, applied
  by hand with `gh api`. `.github/scripts/check-workflows.py` checks the verdict jobs, and fails when a plugin has no
  ruleset file or a file differs from what `--ruleset <plugin>` prints. `docs.yml` runs it too: every ruleset requires
  the `docs` check, so the verdicts are checked on every commit a release tag can point to.

Rejected:

- A bypass for repository admins: the only person who pushes tags is an admin, so the rule would never apply.
- Tags made by a workflow once CI has passed (only the bot may create them): it needs a token with `contents: write`, which
  ADR-0004 keeps out of every workflow, and the release would no longer be tagged by `claude plugin tag`.
- Requiring each job's check (`linux (pytest)`, `validate`, `macos` and so on): an added job would never be required, and a
  renamed one would block every release. One verdict per workflow keeps the rulesets fixed.

## Consequences

- A tag pushed before the release commit's checks have passed is rejected; push it again once they have.
- A tag on a fix commit after a failed release run needs both checks on that commit, and a workflow whose paths the fix
  did not change never starts there: start it by hand (`workflow_dispatch`) before pushing the tag.
- Commits from before this change have no verdict check, so their tags are rejected too: tagging an earlier release means
  setting its ruleset to Disabled for that one push.
- Renaming a workflow or its verdict job blocks that plugin's release tags (docs': every plugin's) until the ruleset file and
  the ruleset on GitHub are changed with it.
- CI never reads the rulesets on GitHub, so a change made in the web interface goes unnoticed. Compare them with the files,
  and spot a tag ruleset no file describes, with `check-workflows.py --live` ([Release a plugin](../internals/release.md)).
- A new plugin needs its ruleset file and its ruleset on GitHub ([Add a plugin](../internals/add-a-plugin.md)).
