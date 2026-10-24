# AGENTS.md — claude-plugins (single source of truth)

## 1. Project identity

The `jack1913` Claude Code plugin marketplace: one public repo whose `plugins/` folder holds every plugin (batbelt,
brand-creator, swift), each one self-contained and versioned on its own.

## 2. Repo layout

| Path | Purpose |
| --- | --- |
| `.claude-plugin/marketplace.json` | The marketplace `jack1913`; every `source` is `./plugins/<name>` |
| `plugins/<name>/` | One plugin: its own `.claude-plugin/plugin.json`, docs and version, and its own tests and changelog (batbelt: tests in the root `tests/`) |
| `.github/workflows/` | One workflow per plugin, plus `marketplace.yml` and `docs.yml` (the docs standard) |
| `.github/scripts/` | Helpers the workflows call |
| `tests/` | batbelt's tests (the other plugins keep theirs in their own folder) |
| `docs/manual/` | Consumer documentation for the marketplace only — choose, install, one card per plugin, troubleshooting, glossary (`docs/internals/docs-standard.md`) |
| `docs/internals/` | Contributors only — layout, tests, adding a plugin, release, the docs standard |
| `docs/adr/` | Architecture Decision Records for the marketplace (a plugin keeps its own) |
| `docs/archive/` | Frozen point-in-time records |
| `.claude/rules/` | Path-scoped constraints, auto-loaded when a matching file is read |
| `.claude/skills/` | Invoked procedures and reference packs |

## 3. Pointer index (source-of-truth → path)

| What | Where |
| --- | --- |
| Plugins listed in the marketplace | `.claude-plugin/marketplace.json` (`plugins[]`) |
| What the marketplace check enforces | `.github/scripts/check-marketplace.py` (module docstring) |
| What the workflow check enforces (triggers, filters, runners, permissions, cancellation) | `.github/scripts/check-workflows.py` (module docstring) |
| A plugin's version (its only home) | `plugins/<name>/.claude-plugin/plugin.json` (`version`) |
| How each plugin is tested in CI | `.github/workflows/<name>.yml` (`run:` lines) |
| What the docs check enforces | `.github/scripts/check-docs-standard.py` (module docstring), `.markdownlint-cli2.yaml`, `lychee.toml` |
| batbelt's tests | `tests/test_plugin.py`, `tests/test_onboard_repo.py`, `tests/test_permission_plan.py` |
| onboard-repo (source of truth for the stamped skills below) | `plugins/batbelt/skills/onboard-repo/` |
| Working on swift | `plugins/swift/AGENTS.md` (it has its own `.claude/` skills, rules and settings) |
| Working on brand-creator | `plugins/brand-creator/AGENTS.md` (script contract: `plugins/brand-creator/scripts/CONTRACT.md`; decisions: `plugins/brand-creator/docs/adr/README.md`, archived log: `plugins/brand-creator/docs/archive/decisions-log.md`) |
| How any doc is written and where it lives (root and every plugin) | `docs/internals/docs-standard.md`, templates in `docs/internals/templates/` |
| Agent instruction layout, rule-vs-skill decision rule | `docs/internals/agent-instructions.md` |
| How to add a plugin (folder, entry, workflow, checks) | `docs/internals/add-a-plugin.md` |
| Repository layout | `docs/internals/layout.md` |
| How each plugin's tests run | `docs/internals/tests.md` |
| How a plugin release is cut and tagged | `docs/internals/release.md` |
| Install, update, remove (the only home for install facts) | `docs/manual/getting-started/install-a-plugin.md` |
| How to contribute; how to report a security problem | `CONTRIBUTING.md`, `SECURITY.md` |

### Auto-loaded rules

Each loads only when Claude reads a file matching its `paths:` frontmatter, so an
unscoped rule taxes every session. Keep this table in step with `.claude/rules/`.

| When you need... | Where to look |
| --- | --- |
| CI workflow shape: push on main only, matching `paths:` filters, pinned runners, read-only token (`.github/workflows/*.yml`) | `.claude/rules/ci-workflow-per-plugin.md` |

### Skills

Invoked with the `Skill` tool, or by name. A skill's body costs nothing until it is
invoked, so reference material belongs here rather than in a rule.

| Skill | When to use |
| --- | --- |
| `changelog-release` | Cut a release of ONE plugin: its `CHANGELOG.md` and `plugin.json` version (hands swift to `plugins/swift/.claude/skills/changelog-release`) |
| `update-docs` | Bring `README.md`, `AGENTS.md` and `docs/` back in line with the repo |
| `update-rules` | Repair the claims inside `.claude/rules` and `.claude/skills` |

## 4. Project constraints

- A change to one plugin stays inside `plugins/<name>/` (plus its workflow, and `tests/` for batbelt). Each plugin's own
  `AGENTS.md`, `CLAUDE.md` or `README.md` has the rules for working on it.
- Adding a plugin: follow `docs/internals/add-a-plugin.md` —
  folder, marketplace entry, workflow, then `python3 .github/scripts/check-marketplace.py`,
  `python3 .github/scripts/check-workflows.py`,
  `claude plugin validate . --strict` and `claude plugin validate plugins/<name> --strict`. Write the new workflow by
  copying an existing one: `push` on `main` only, `pull_request` and `workflow_dispatch`, the same `paths:` list on
  both, a pinned runner and `permissions: contents: read` (`.claude/rules/ci-workflow-per-plugin.md` owns this; a `paths:` rule fires on Read,
  not on creating a file, so this line carries it).
- Release tags are `<name>--vX.Y.Z`, made with `claude plugin tag plugins/<name>` from the repo root, never `git tag`,
  and only once every CI run of the release commit on `main` has passed (a tag push runs no CI; `docs/internals/release.md`).
- Docs describe implemented state, and follow `docs/internals/docs-standard.md` (layout, voice, skill descriptions,
  changelogs, ADRs) — in every plugin too.
- `docs/archive/**` is frozen — never edited.
- A stale pointer is worse than no pointer: moving or renaming a **doc, rule or
  skill** means fixing its row above in the same change. Nothing fails a build when
  these tables drift.

## 5. Documentation map

`docs/manual/` (consumer) · `docs/internals/` (technical) · `docs/adr/` (decisions) · `docs/archive/` (frozen).
