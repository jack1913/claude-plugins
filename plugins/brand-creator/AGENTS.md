# AGENTS.md — brand-creator plugin (pointer index)

brand-creator is a Claude Code plugin in `plugins/brand-creator/` of the monorepo `jack1913/claude-plugins`. It runs a
brand-identity project as a step-by-step process with owner decisions. Paths below are relative to this folder, except
the workflow and docs standard rows, which are from the repository root.

No `CLAUDE.md` at this folder's root: `claude plugin validate --strict` rejects one.

## Pointer index

| What | Where |
| --- | --- |
| Plugin manifest, the only version home | `.claude-plugin/plugin.json` |
| Skills (the process, naming, assets, book; the thin command wrappers) | `skills/<name>/SKILL.md` |
| The orchestrator skill and its phase files | `skills/brand-creator/SKILL.md`, `skills/brand-creator/references/phases/` |
| The other references (board contract, fleet, cascade, platform specs) | `skills/brand-creator/references/` |
| The worked example brand (Acme) | `skills/brand-creator/references/examples/acme/` |
| Agents (opt-in, started by workflows) | `agents/` |
| Workflows (directions, review-panel, naming, adopt) | `workflows/` |
| Entry point the skills call | `bin/brand-creator` |
| Scripts and emitters | `scripts/`, `scripts/emitters/` |
| The script contract: reports, exit codes, every tool's rules | `scripts/CONTRACT.md` |
| The safety hook and its guard | `hooks/hooks.json`, `scripts/guard.py` |
| Files copied into brand projects (not docs) | `templates/` |
| Tests | `tests/` (pytest in `tests/test_*.py`, `tests/node/`, `tests/smoke/`, `tests/docker/`) |
| How CI runs them | `.github/workflows/brand-creator.yml` (`run:` lines; Linux in Docker, validate, macOS) |
| Evals (behaviour cases, billed) and trigger evals | `evals/`, `evals/trigger-evals.json` |
| Connector rules (none needed) | `CONNECTORS.md` |
| Third-party notices | `THIRD_PARTY_NOTICES.md` |
| Licence | `LICENSE` |
| Changelog | `CHANGELOG.md` |
| Docs folders | `docs/README.md` |
| Manual index | `docs/manual/README.md` |
| Every command, workflow and agent | `docs/manual/reference/commands.md` |
| Development, evals, manual checks | `docs/internals/README.md` |
| Decision records | `docs/adr/README.md` |
| Frozen build history | `docs/archive/README.md` |
| Docs standard | `docs/internals/docs-standard.md` |

## Rules for working here

- A change stays inside `plugins/brand-creator/`, plus `.github/workflows/brand-creator.yml`.
- Run the tests from this folder: `uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q -n 4`.
  Tests that need a set-up data directory skip with a NOT VERIFIED banner; a skip is not a pass.
- Do not bump `version` in `plugin.json` except when releasing. Release with the `changelog-release` skill at the
  repository root.
- Files under `templates/` and `evals/` are copied into other projects or graded by the eval runner. Do not edit them as
  docs.
- `scripts/CONTRACT.md` is read by skills, scripts and tests by that path. Do not move it.
- New decisions are ADRs in `docs/adr/`. `docs/archive/` is frozen.
- A renamed or removed skill or document needs its row above fixed in the same change.
