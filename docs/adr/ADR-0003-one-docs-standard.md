# ADR-0003: One docs standard for the marketplace and every plugin

- **Status:** accepted
- **Date:** 2026-10-19
- **Source:** [`docs/internals/docs-standard.md`](../internals/docs-standard.md); the Context below
  records the findings of the docs review that led to it

## Context

The three plugins documented themselves three ways: swift had a full `docs/` tree, batbelt a README
and one internals page, brand-creator a 358-line README with `dev/` logs and no `docs/`. Each
plugin's user guide was also hand-copied into the marketplace's `docs/manual/use/<plugin>.md`, and
the copies had drifted (batbelt's README said four commands, its manual page three). Maintainer
pages sat in the user manual. Skill descriptions, which users read in the `/` menu, used four styles.
The voice rule lived only inside the `update-docs` skill, and no CI check covered any of it.

## Decision

- One standard, [`docs/internals/docs-standard.md`](../internals/docs-standard.md), for the root and
  every plugin: Diátaxis page kinds, the same `docs/` layout per plugin, one home per fact, one voice,
  one pattern for skill, agent and plugin metadata, Keep a Changelog, and one ADR format.
- **Each plugin owns its manual** in `plugins/<name>/docs/manual/`. The marketplace manual keeps only
  cross-plugin pages and one short card per plugin that links into it.
- Maintainer pages live in `docs/internals/`, never in `docs/manual/`.
- CI enforces it (`docs.yml`): markdownlint, an offline link check and a repo script for the
  metadata, changelog, ADR and pointer rules, first as warnings, failing once every area is in
  line. Vale may follow, as warnings.

Rejected:

- The marketplace as the manual's home, with plugin READMEs reduced to a link: plugins stop being
  self-contained, against ADR-0001.
- Keeping each plugin's own layout: the drift above is what that produced.
- MADR for ADRs: the existing short template already records context, decision and consequences;
  it gains a status grammar and an update rule instead.

## Consequences

- batbelt and brand-creator gain a `docs/` tree and an `AGENTS.md`; brand-creator's long README is
  split into manual and internals pages and its `dev/` logs move to `docs/archive/`.
- swift moves its contributor pages out of its manual, moves its shipped `docs/superpowers/` specs
  and plans to `docs/archive/`, and moves its ADR template and status lines to the new grammar.
- Display fields move to `plugin.json` only; marketplace entries keep `name`, `source`, `category`
  and `tags`.
- `docs/manual/use/<plugin>.md` stop restating plugin READMEs; the marketplace gains
  `CONTRIBUTING.md`, `SECURITY.md`, troubleshooting and a glossary.
- batbelt's `onboard-repo` templates are updated so repositories it sets up get the same standard.
