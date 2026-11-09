# ADR-0008: CI runs quick checks; the full suite runs before a release, on the maintainer's machine

- **Status:** accepted
- **Date:** 2026-11-06
- **Source:** the job times of brand-creator's runs on 2026-11-05 and 2026-11-06; the account's Actions usage page for
  November 2026; `.github/workflows/brand-creator.yml`; `plugins/brand-creator/docs/internals/manual-checks.md`

## Context

brand-creator's workflow ran its whole suite on every push: three Linux jobs (pytest, node, smoke), each building the same
Docker image, about 26, 11 and 8 minutes, so about 47 minutes per push. Until 2026-11-04 it also ran macOS jobs. From
2026-11-01 to 2026-11-06 the repository used 440 Linux minutes and 242 macOS minutes, $17.64 at list price. Nothing was
billed, because the repository is public, but on 2026-11-06 the account could no longer start Actions jobs, and a release
tag cannot be pushed without its checks. The suite already runs in full on the maintainer's Mac and in the same Linux
Docker image before each release, and that run is recorded.

## Decision

- brand-creator's workflow runs one job and its verdict: `claude plugin validate --strict` and the quick tests (the
  manifest and version pins, skill and agent frontmatter, hooks, eval cases, the workflow's own shape and the paid-test
  guard), about a minute of tests. Any skip fails the job; the two tests that need a set-up data directory or the private
  denylist are deselected by name.
- No workflow runs on macOS or builds the Docker image.
- Before each brand-creator release tag, the full suite runs on the release commit on a Mac (`tests/run-all.sh --smoke`)
  and in the Linux Docker image (`tests/docker/run.sh`), and the result is recorded in that plugin's `manual-checks.md`
  ("Release run"). The tag rulesets still require the `brand-creator` and `docs` checks.

Rejected:

- Keeping the three Linux jobs and building the image once: still about 40 minutes per push.
- Running the full suite only on a schedule: it would still spend minutes on commits nobody releases.

## Consequences

- A push that breaks a test outside the quick set passes CI; the release run catches it before the tag, not at the push.
- A release needs the maintainer's machine: a Mac with Xcode, and Docker.
- The image build, `verify_log.py` and the parts of `run-all.sh` stay, used by the local Linux run.
- This replaces the CI part of [ADR-0004](ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md) that names a
  `macos-26` runner; its triggers and tag rules are unchanged.

## Update 2026-11-09

The Linux part of brand-creator's release run may be limited to the test files the release touches
(`BRAND_CREATOR_TEST_PARTS=pytest BRAND_CREATOR_TEST_FILES="tests/test_<name>.py ..." tests/docker/run.sh`), when the release
changes nothing that renders (Chromium, resvg, ImageMagick, Ghostscript, the PDF and PowerPoint exports), nothing in the Docker
image or in `setup`, and no handling of file names whose bytes differ between the two systems (decomposed letters, letter case).
Otherwise the full Linux run stands. The Mac part stays the full suite with the smoke. The release record says which Linux run
was made. The owner chose it for 0.11.1: the full Linux run takes about 20 minutes, the limited one under 2. For daily work,
`tests/run-all.sh --fast` leaves out every test that took a second or more in the last measured run (`tests/durations.json`)
and says how many; it never replaces a release run.
