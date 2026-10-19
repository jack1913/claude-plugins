---
paths:
  - ".github/workflows/*.yml"
description: "CI workflows: one per plugin, push + pull_request + workflow_dispatch, identical paths filters, read-only token"
---

# CI workflows

- Every workflow triggers on `push`, `pull_request` and `workflow_dispatch`, and the
  `paths:` list under `push` is identical to the one under `pull_request`.
- A plugin's workflow is `.github/workflows/<name>.yml`, and its filter lists
  `plugins/<name>/**` plus the workflow file itself. batbelt's also lists `tests/**` and
  `.claude-plugin/**`, because its tests live in the root `tests/` and
  `tests/test_plugin.py` reads `.claude-plugin/marketplace.json`.
- Every workflow declares `permissions: contents: read`.

Only `brand-creator.yml` is checked, and only partly:
`plugins/brand-creator/tests/test_docker_ci.py:139` (read-only token) and `:141` (both
filters name the plugin folder and the workflow file). `.github/scripts/check-marketplace.py`
reads only `marketplace.json` and `plugins/`, so `batbelt.yml`, `swift.yml` and
`marketplace.yml` are unchecked. A wrong filter makes a plugin's CI silently skip its own
changes, or runs the expensive macOS job in `brand-creator.yml` on unrelated pushes.

Re-derive:
`rg -c 'workflow_dispatch:' .github/workflows` (1 per file, 4 files);
`rg -n -A1 '^permissions:' .github/workflows | rg -c 'contents: read'` (4).
