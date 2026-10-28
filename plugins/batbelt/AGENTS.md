# AGENTS.md — batbelt plugin (pointer index)

batbelt is a Claude Code plugin in `plugins/batbelt/` of the monorepo `jack1913/claude-plugins`. It ships four skills: `grill-me`, `prove-it`, `onboard-repo` and `puppet-master`. Paths below are relative to this folder, except the tests, workflow and docs standard rows, which are from the repository root.

No `CLAUDE.md` at this folder's root: `claude plugin validate --strict` rejects one.

## Pointer index

| What | Where |
| --- | --- |
| Plugin manifest, the only version home | `.claude-plugin/plugin.json` |
| `grill-me` (starts by typing or by saying "grill me") | `skills/grill-me/SKILL.md` |
| `prove-it` | `skills/prove-it/SKILL.md` |
| prove-it references | `skills/prove-it/references/` |
| `onboard-repo` (typed only) | `skills/onboard-repo/SKILL.md` |
| onboard-repo long sections, indexed | `skills/onboard-repo/references/_index.md` |
| onboard-repo helper scripts | `skills/onboard-repo/scripts/` |
| Files onboard-repo stamps into other repositories | `skills/onboard-repo/templates/` |
| `puppet-master` | `skills/puppet-master/SKILL.md` |
| puppet-master's worker brief template | `skills/puppet-master/worker-brief.md` |
| puppet-master's analyst brief template (its tags must equal `TAGS` in `analyst.mjs`) | `skills/puppet-master/analyst-brief.md` |
| puppet-master's helper (Node, built-ins only) | `skills/puppet-master/scripts/puppet.mjs`, with `harvest.mjs` (logs folder, redaction, events) and `analyst.mjs` (findings, summary, decisions) |
| puppet-master's logs-folder option | `.claude-plugin/plugin.json` (`userConfig.puppet_logs_dir`) |
| Licence | `LICENSE` |
| Changelog | `CHANGELOG.md` |
| Docs folders | `docs/README.md` |
| Manual index | `docs/manual/README.md` |
| Every command and argument | `docs/manual/reference/commands.md` |
| How each skill works | `docs/internals/README.md` |
| Tests (in the root `tests/`, not here) | `tests/test_plugin.py`, `tests/test_onboard_repo.py`, `tests/test_permission_plan.py`, `tests/test_review_fixes.py`, `tests/test_puppet_master.py` (runs `tests/puppet_master/*.test.mjs`; needs `node` 20+) |
| CI workflow | `.github/workflows/batbelt.yml` |
| Docs standard | `docs/internals/docs-standard.md` |

## Rules for working here

- A change stays inside `plugins/batbelt/`, plus `tests/` and `.github/workflows/batbelt.yml`.
- Run the tests from the repository root: `uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q`.
- Do not bump `version` in `plugin.json` except when releasing. Release with the `changelog-release` skill at the repository root.
- Files under `skills/onboard-repo/templates/` are stamped into other repositories. Do not edit them as docs.
- A renamed or removed skill or document needs its row above fixed in the same change.
