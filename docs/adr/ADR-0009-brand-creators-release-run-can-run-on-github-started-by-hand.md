# ADR-0009: brand-creator's release run can run on GitHub, started by hand

- **Status:** accepted
- **Date:** 2026-11-17
- **Source:** `.github/workflows/brand-creator-release.yml`; `.github/scripts/check-workflows.py`; the `macos-suite` and
  `linux-suite` jobs of `.github/workflows/brand-creator.yml` as they ran until 2026-11-04 (commit b621a96);
  `plugins/brand-creator/docs/internals/manual-checks.md` ("Release run"); the 0.12.0 release prepared on a Linux machine
  on 2026-11-17

## Context

[ADR-0008](ADR-0008-ci-runs-quick-checks-the-full-suite-runs-before-a-release.md) took brand-creator's full suite out of
CI and gave it to the maintainer's machine: a Mac with Xcode, and Docker. A release prepared on a Linux machine on
2026-11-17 could not be finished there, for three reasons:

- 48 tests need Apple's tools (`sips`, `iconutil`, `actool`, `assetutil`, the `.icon` pipeline), which exist only on macOS.
- The anonymisation test needs the private denylist, and that file was on the Mac only.
- Two tests failed on that machine for reasons of their own: one could not hide a `uv` installed in `/usr/bin`, the other
  expected the summary line of an older Claude Code. Neither is about Linux; both are fixed in the plugin.

GitHub ran the Mac half before: until 2026-11-04 the workflow had a `macos-26` job and the Docker jobs. ADR-0008 removed
them because they ran on every push, not because they did not work.

## Decision

- `brand-creator-release.yml` is brand-creator's release run on GitHub's runners. It starts only by hand
  (`workflow_dispatch`), on the release commit: `gh workflow run brand-creator-release.yml --ref main`. It never starts on a
  push, a pull request or a tag.
- Its `macos` jobs run the whole suite on `macos-26`: pytest in three shares of the test files, dealt out by measured time
  (`tests/tiering.py shard`), and one job for node:test and the smoke. Any skip fails. Its `linux` jobs run the suite in
  the Linux Docker image, where only the expected off-macOS skips pass. Its verdict is the check `brand-creator-release`.
- A release run is that workflow's run on the release commit, or the run on a Mac with Docker that ADR-0008 describes. The
  release record names which, with the run's number.
- The run needs no private file: the scan for private terms is no longer a test
  ([ADR-0010](ADR-0010-private-terms-are-kept-out-by-their-holders-pre-push-scan.md)).
- `check-workflows.py` accepts one `<plugin>-release.yml` per plugin: a release run, which triggers on `workflow_dispatch`
  and nothing else. Every other rule holds for it: a pinned runner image, a timeout of an hour at most on every job,
  read-only permissions, a run that is never cancelled, and a verdict job named after the workflow.
- The release-tag rulesets stay as they are: a tag needs the checks `brand-creator` and `docs`, not `brand-creator-release`.

Rejected:

- The release-run jobs inside `brand-creator.yml`, under a condition: on a push they would be skipped, and a verdict that
  needs a skipped job fails.
- A Mac run only for a release that changes the code calling Apple's tools: the rest of the suite would never run on
  macOS, where most of the plugin's users are.
- Requiring `brand-creator-release` in the tag ruleset now: nobody can bypass a ruleset, so one job that fails for a
  reason of GitHub's runner would block every release. It can be required once the workflow has passed on several
  releases in a row.

## Consequences

- A release can be cut from any machine that has `gh`, signed in, by anyone who may push to `main`.
- This replaces two parts of ADR-0008: "No workflow runs on macOS or builds the Docker image" now holds for every
  workflow that starts on a push or a pull request, and a release no longer needs the maintainer's machine. Its quick
  checks on every push, and its update on a limited Linux run, are unchanged.
- A release run uses four macOS jobs and two Linux jobs, hours of runner time in all. ADR-0008 records that on 2026-11-06
  the account could no longer start Actions jobs after six days of per-push runs. If that happens again, the run on a Mac
  with Docker is still a release run.
- Nothing but the release procedure makes anyone start the workflow: a tag is accepted without it.
- On the date of this record the workflow has not run yet. Its first run is recorded in brand-creator's
  `manual-checks.md` ("Release run"); until it passes, a release takes the Mac path.
