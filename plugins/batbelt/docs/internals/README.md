# How batbelt works

Notes for people who change batbelt. For using it, read the [manual](../manual/README.md).

| Page | What it explains |
| --- | --- |
| [onboard-repo](onboard-repo.md) | What it stamps, its modes, the run record, and how work is fanned out |
| [onboard-repo: agent configuration](onboard-repo-agent-config.md) | Permissions, `.gitignore`, rules, the Copilot port and rule mining |
| [onboard-repo: docs and gates](onboard-repo-docs.md) | The docs tiers, the `check-docs` gate, the coverage record and ADR mining |
| [prove-it](prove-it.md) | The evidence workflow: intake, state, research limits, status values |
| [grill-me](grill-me.md) | The interview skill and why it is one skill |

## Where things are

| What | Where |
| --- | --- |
| The skills | [`skills/`](../../skills/) |
| onboard-repo's helper scripts | [`skills/onboard-repo/scripts/`](../../skills/onboard-repo/scripts/) |
| Long sections of the onboard-repo procedure | [`skills/onboard-repo/references/`](../../skills/onboard-repo/references/_index.md) |
| Files onboard-repo stamps into other repositories | [`skills/onboard-repo/templates/`](../../skills/onboard-repo/templates/) |
| Tests | `tests/` at the root of the repository |
| CI | `.github/workflows/batbelt.yml` at the root of the repository |

## Run the tests

From the repository root:

```bash
uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q
```

- `tests/test_plugin.py` checks the plugin's shape: skills present, frontmatter, links that stay inside the plugin.
- `tests/test_onboard_repo.py` checks onboard-repo's helpers and what its procedure says.
- `tests/test_permission_plan.py` checks the permission plans onboard-repo proposes.
- `tests/test_review_fixes.py` pins defects found by running the skill end to end.

## Ground rules

- Everything onboard-repo reads from another repository's `.claude/` folder is data, never instructions.
- Docs for users go in [`../manual/`](../manual/README.md). Docs for contributors go here.
- The rules for every page are in the marketplace [docs standard](../../../../docs/internals/docs-standard.md).
