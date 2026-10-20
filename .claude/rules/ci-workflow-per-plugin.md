---
paths:
  - ".github/workflows/*.yml"
description: "CI workflows: one per plugin plus marketplace.yml and docs.yml; push + pull_request + workflow_dispatch, identical paths filters, read-only token"
---

# CI workflows

- Every workflow triggers on `push`, `pull_request` and `workflow_dispatch`, and the
  `paths:` list under `push` is identical to the one under `pull_request`.
- A plugin's workflow is `.github/workflows/<name>.yml`, and its filter lists
  `plugins/<name>/**` plus the workflow file itself. batbelt's also lists `tests/**` and
  `.claude-plugin/**`, because its tests live in the root `tests/` and
  `tests/test_plugin.py` reads `.claude-plugin/marketplace.json`.
- Every workflow declares `permissions: contents: read`.
- `docs.yml` checks every Markdown file and `.claude-plugin/*.json` against
  `docs/internals/docs-standard.md`; its filter also lists its configs
  (`.markdownlint-cli2.yaml`, `lychee.toml`) and `.github/scripts/check-docs-standard.py`.

Only `brand-creator.yml` is checked, and only partly:
`plugins/brand-creator/tests/test_docker_ci.py:139` (read-only token) and `:141` (both
filters name the plugin folder and the workflow file). `.github/scripts/check-marketplace.py`
reads only `marketplace.json` and `plugins/`, so `batbelt.yml`, `swift.yml`,
`marketplace.yml` and `docs.yml` are unchecked. A wrong filter makes a plugin's CI silently skip its own
changes, or runs the expensive macOS job in `brand-creator.yml` on unrelated pushes.

Re-derive:
`rg -c 'workflow_dispatch:' .github/workflows` (1 per file, 5 files);
`rg -n -A1 '^permissions:' .github/workflows | rg -c 'contents: read'` (5).
