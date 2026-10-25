---
paths:
  - ".github/workflows/*.yml"
  - ".github/rulesets/*.json"
description: "CI workflows: one per plugin plus marketplace.yml and docs.yml; push on main only + pull_request + workflow_dispatch, identical paths filters, pinned runners, read-only token, main runs never cancelled, one verdict job named after the workflow, one release-tag ruleset per plugin"
---

# CI workflows

- Every workflow triggers on `push`, `pull_request` and `workflow_dispatch`, and on nothing else
  (`create` or `release` would run on a tag). `push` has
  `branches:` with exactly `main`, so a tag push runs no workflow (GitHub evaluates no path
  filter for a tag), and its `paths:` list is identical to the one under `pull_request`.
- A plugin's workflow is `.github/workflows/<name>.yml`, and its filter lists
  `plugins/<name>/**` plus the workflow file itself. batbelt's also lists `tests/**` and
  `.claude-plugin/**`, because its tests live in the root `tests/` and
  `tests/test_plugin.py` reads `.claude-plugin/marketplace.json`.
- Every workflow declares `permissions: contents: read` at the top level, and no job sets
  its own permissions; jobs run on pinned images (`ubuntu-24.04`, `macos-26`), never a
  label with `latest`.
- A run on `main` is never cancelled or replaced: `concurrency` is top-level only, its
  `group` holds `github.sha` (one group per commit), and `cancel-in-progress` is `false` or
  `${{ github.event_name == 'pull_request' }}`.
- Test tools come pinned, with everything they need, from the suite's `tests/requirements.txt`
  (compiled by uv from `tests/requirements.in`; `uv run --no-project --with-requirements
  tests/requirements.txt`), and `setup-uv` pins the uv version of the Linux test image.
- `docs.yml` checks every Markdown file and `.claude-plugin/*.json` against
  `docs/internals/docs-standard.md`; its filter also lists its configs
  (`.markdownlint-cli2.yaml`, `lychee.toml`) and `.github/scripts/check-docs-standard.py`.
- Every workflow has one job named after it (no `name:` or condition of its own), its verdict;
  for a plugin's workflow and `docs.yml` it is the check a release tag needs. In a workflow of
  several jobs it needs every other job, runs `if: ${{ always() }}`, and its steps are exactly
  `VERDICT_STEPS` of `check-workflows.py` (they fail unless every job it needs succeeded). No
  other job's check carries a workflow's name. `docs.yml` runs `check-workflows.py`: every
  ruleset requires `docs`, so the verdicts are checked on every commit a tag can point to.
- Every plugin has `.github/rulesets/<name>-release-tags.json`, exactly what
  `check-workflows.py --ruleset <name>` prints: a tag `<name>--v*` needs the checks `<name>` and
  `docs` from GitHub Actions. GitHub keeps its own copy; changing a file means changing that
  copy with `gh api` too (`docs/internals/release.md`, "The tag rulesets").

`.github/scripts/check-workflows.py` enforces the triggers, the filters a plugin's workflow
needs, the permissions, the runners, the concurrency groups, the cancellation and the verdict
job of every workflow, `.yaml` files included, and the ruleset files; `marketplace.yml`
runs it on any change under `.github/workflows/` or `.github/rulesets/`, with `--self-test`.
It does not check batbelt's extra filters, the docs.yml filter, the requirements files, the uv
version, or the rulesets on GitHub (`--live` compares those by hand, and reports a tag ruleset
no file describes). Why:
`docs/adr/ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md`,
`docs/adr/ADR-0005-release-tags-need-a-passing-ci-verdict.md`.

Re-derive:
`python3 .github/scripts/check-workflows.py` (5 workflows and 3 release-tag rulesets checked, 0 errors);
`python3 .github/scripts/check-workflows.py --self-test` (every rule broken on purpose is caught);
`python3 .github/scripts/check-workflows.py --live` (3 release-tag rulesets on GitHub compared with their files, 0 errors).
