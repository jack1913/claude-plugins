---
paths:
  - ".github/workflows/*.yml"
description: "CI workflows: one per plugin plus marketplace.yml and docs.yml; push on main only + pull_request + workflow_dispatch, identical paths filters, pinned runners, read-only token, main runs never cancelled"
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

`.github/scripts/check-workflows.py` enforces the triggers, the filters a plugin's workflow
needs, the permissions, the runners, the concurrency groups and the cancellation of every
workflow, `.yaml` files included; `marketplace.yml`
runs it on any change under `.github/workflows/`, with `--self-test`. It does not check
batbelt's extra filters, the docs.yml filter, the requirements files or the uv version. Why:
`docs/adr/ADR-0004-ci-runs-on-main-and-pull-requests-never-on-tags.md`.

Re-derive:
`python3 .github/scripts/check-workflows.py` (5 workflows checked, 0 errors);
`python3 .github/scripts/check-workflows.py --self-test` (every rule broken on purpose is caught).
