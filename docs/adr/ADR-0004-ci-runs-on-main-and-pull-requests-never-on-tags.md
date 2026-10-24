# ADR-0004: CI runs on main and pull requests, never on tags; a release is tagged after its CI passes

- **Status:** accepted
- **Date:** 2026-10-24
- **Source:** this repository's Actions history from 2026-10-19 to 2026-10-24; GitHub's workflow syntax for `on.push`
  (branches, tags and paths filters, "Path filters are not evaluated for pushes of tags"); the CI workflows of CPython,
  uv, ruff and Flask; `.github/scripts/check-workflows.py`

## Context

Every workflow ran on `push` with only a `paths:` filter. GitHub evaluates no path filter for a tag push, so each release
tag started all five workflows again, the unrelated plugins' included: 17 tag pushes started 82 of the 137 runs between
2026-10-19 and 2026-10-24, and the brand-creator runs among them took 46% of that workflow's run time.

The tag run also hid two gaps. `brand-creator--v0.3.5` was tagged on a commit whose CI on `main` had failed: the tag
lands seconds after the push, long before CI ends, so it never gated anything. And a run on `main` (64e5f78) was
cancelled by the next push (`cancel-in-progress: true` per ref), which left that commit with no verdict of its own.

Runner images were `-latest` labels, which GitHub moves to a new OS over one to two months, and the test tools were
installed unpinned, so a run could turn red without a commit.

## Decision

- Every workflow runs on `push` to `main`, on `pull_request` and on `workflow_dispatch`, with the same `paths:` filter on
  push and pull_request. `push.branches` is exactly `main`, so a tag push starts no workflow: a workflow that defines
  only branches does not run for tags. This is the shape of CPython's, uv's, ruff's and Flask's CI.
- A run on `main` is never cancelled. Only a superseded pull-request run is
  (`cancel-in-progress: ${{ github.event_name == 'pull_request' }}`, one concurrency group per pull request or commit).
- A release is tagged only after every CI run of its commit on `main` has passed
  ([Release a plugin](../internals/release.md)).
- Runner images are pinned (`ubuntu-24.04`, `macos-26`), and so are uv (the version the Linux test image uses) and the
  Python test tools with every package they need (`tests/requirements.txt` of each test suite, compiled by uv from its
  `tests/requirements.in`, read with `uv run --with-requirements`). Node is pinned to its major version.
- `.github/scripts/check-workflows.py` enforces the triggers, filters, permissions, runners, concurrency groups and
  cancellation of every workflow. `marketplace.yml` runs it on any workflow change, with `--self-test`, which breaks
  each rule on purpose and fails unless the check catches it.

Rejected:

- Running the suite on the tag as the release gate: it never gated (v0.3.5), and it doubled the CI of every release.
- A separate workflow that publishes on a tag: nothing is built or published; a release reaches users when its version
  bump lands on `main` ([ADR-0002](ADR-0002-per-plugin-versions-and-tags.md)).
- Required status checks with a pull-request flow: they reject direct pushes to `main`, which is how releases land
  today. Revisit, with one gate job that needs every job, when pull requests become the flow.

## Consequences

- A push to any branch other than `main` runs no CI. Open a pull request, or start a workflow by hand with
  `gh workflow run <workflow> --ref <branch>`.
- A release costs one CI run instead of two, and its tag points at a commit whose own run passed.
- Pushes to `main` in quick succession run side by side instead of cancelling each other.
- A new runner image, uv or test-tool version is a deliberate commit: the label or version in the workflow, or
  `tests/requirements.in` and the `tests/requirements.txt` compiled from it.
