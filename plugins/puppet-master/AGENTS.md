# AGENTS.md — puppet-master plugin (pointer index)

puppet-master is a Claude Code plugin in `plugins/puppet-master/` of the monorepo `jack1913/claude-plugins`. It ships one skill, `puppet-master`. Paths below are relative to this folder, except the workflow and docs standard rows, which are from the repository root.

No `CLAUDE.md` at this folder's root: `claude plugin validate --strict` rejects one.

## Pointer index

| What | Where |
| --- | --- |
| Plugin manifest, the only version home | `.claude-plugin/plugin.json` |
| The logs-folder option | `.claude-plugin/plugin.json` (`userConfig.puppet_logs_dir`) |
| `puppet-master` (typed only) | `skills/puppet-master/SKILL.md` |
| The worker brief template | `skills/puppet-master/worker-brief.md` |
| The analyst brief template (its tags must equal `TAGS` in `analyst.mjs`) | `skills/puppet-master/analyst-brief.md` |
| The helper (Node, built-ins only) | `skills/puppet-master/scripts/puppet.mjs`, with `harvest.mjs` (logs folder, redaction, events) and `analyst.mjs` (findings, summary, decisions) |
| Licence | `LICENSE` |
| Changelog | `CHANGELOG.md` |
| Docs folders | `docs/README.md` |
| Manual index | `docs/manual/README.md` |
| Every command and option | `docs/manual/reference/commands.md` |
| How it works | `docs/internals/README.md` |
| Tests (`node:test`, no dependencies) | `tests/*.test.mjs`, fixtures in `tests/fixtures/` |
| CI workflow | `.github/workflows/puppet-master.yml` |
| Docs standard | `docs/internals/docs-standard.md` |

## Rules for working here

- A change stays inside `plugins/puppet-master/`, plus `.github/workflows/puppet-master.yml`.
- Run the tests from this folder: `node --test tests/*.test.mjs` (Node 20 or newer).
- A change to `SKILL.md` or a brief gets an assertion in `tests/skill-text.test.mjs`, like the existing ones.
- Do not bump `version` in `plugin.json` except when releasing. Release with the `changelog-release` skill at the repository root.
- A renamed or removed skill or document needs its row above fixed in the same change.
