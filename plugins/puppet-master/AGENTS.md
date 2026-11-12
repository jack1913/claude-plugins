# AGENTS.md — puppet-master plugin (pointer index)

puppet-master is a Claude Code plugin in `plugins/puppet-master/` of the monorepo `jack1913/claude-plugins`. It ships one skill, `puppet-master`. Paths below are relative to this folder, except the workflow and docs standard rows, which are from the repository root.

No `CLAUDE.md` at this folder's root: `claude plugin validate --strict` rejects one.

## Pointer index

| What | Where |
| --- | --- |
| Plugin manifest, the only version home | `.claude-plugin/plugin.json` |
| The logs-folder option | `.claude-plugin/plugin.json` (`userConfig.puppet_logs_dir`) |
| The self-compact switch (`ask`, `on`, `off`) | `.claude-plugin/plugin.json` (`userConfig.self_compact`) |
| The mod that compacts or clears a session (its calls, files and refusals) | `hooks/puppet-mod.js`, listed by `hooks/hooks.json`; how it works: `docs/internals/puppet-master.md` ("The mod") |
| `puppet-master` (typed only): the always-needed core, with the "Files to read, and when" table | `skills/puppet-master/SKILL.md` |
| The text the master reads at one moment (start, jobs, briefs, approvals, context, helper, wrap-up, setup), and the list of those files | `skills/puppet-master/references/`, `skills/puppet-master/references/_index.md` |
| The worker brief template | `skills/puppet-master/worker-brief.md` |
| The analyst brief template (its tags must equal `TAGS` in `analyst.mjs`) | `skills/puppet-master/analyst-brief.md` |
| The user's setup prerequisites the master reads on demand | `skills/puppet-master/references/setup-prerequisites.md` |
| The helper (Node, built-ins only) | `skills/puppet-master/scripts/puppet.mjs`, with `harvest.mjs` (logs folder, redaction, events) and `analyst.mjs` (findings, summary, decisions); `compact`, `clear` and the mod's files are in `puppet.mjs` ("the mod" section) |
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

## Where skill text goes

`SKILL.md` is read in full once, and after a compaction Claude Code keeps only its first 5,000 tokens. So it holds
only what the master needs on every turn; the rest sits in `skills/puppet-master/references/`, one file per moment.
`tests/skill-text.test.mjs` fails a `SKILL.md` body over 300 lines and a reference file over 200 (the docs gate's
limit is 500), and a reference file over 100 lines needs a `## Contents` list.

| The text is needed | It goes in |
| --- | --- |
| on every turn, or it is a red flag | `SKILL.md` |
| at the start of the day, or when a second master starts | `skills/puppet-master/references/on-start.md` |
| when giving a job: the detail of rules 3, 4, 5 and 12, a design to relay, chained jobs | `skills/puppet-master/references/jobs.md` |
| when writing a brief, or quoting the user from an earlier day | `skills/puppet-master/references/briefs.md` |
| when putting an approval, an irreversible step, a `!` line or an outside-service step to the user | `skills/puppet-master/references/approvals.md` |
| when compacting, clearing or switching a session, or at the master's own context: the detail of rules 7, 9 and 10 | `skills/puppet-master/references/context.md` |
| for a helper command or its output | `skills/puppet-master/references/helper.md` |
| when the user ends the day | `skills/puppet-master/references/wrap-up.md` |
| when a setting, the mod's needs or a `PUPPET_*` variable comes up | `skills/puppet-master/references/setup-prerequisites.md` |

- A rule's detail moves only under its rule number (`## Rule N in detail`) and is never renumbered; a section keeps its
  heading wherever it lives. `SKILL.md` keeps the rule's first sentence and ends it with "Detail: `references/<file>`, rule N."
- A new moment gets a new reference file, a row in `references/_index.md` and a row in `SKILL.md`'s "Files to read,
  and when" table, in the same change.
- A file at its budget is split by moment, never trimmed of rules the user approved.
- No reference links another reference, and none holds a `${…}` placeholder: a reference is read raw.
- The analyst's proposals name their home in this table (`analyst-brief.md`), so the user approves where a change goes
  together with the change.
