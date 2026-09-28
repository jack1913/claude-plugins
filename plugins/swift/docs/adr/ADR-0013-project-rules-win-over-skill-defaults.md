# ADR-0013: A project's own rules win over the code skills' defaults

- **Status:** accepted
- **Date:** 2026-09-28
- **Source:** the example-app session's report (2026-09-28): `swift:concurrency` recommends `async let` for fixed parallel work, and example-app forbids it with its typed-throws client; eval `project-rule-over-skill` (commit `c5d301b`); commits `733ff08` (`swift:concurrency`), `7cef39c` (`swift:swiftui`), `ab2e9fd` (`swift:testing`); ADR-0007 (the design-literal rule this sits beside)

## Context

ADR-0007 made a project's design layer win over the plugin's example literals, and three skills carry that rule. It covers design literals only. The code skills also give defaults: `swift:concurrency`'s tool table picks `async let` for fixed parallel work, and `swift:testing`'s contract sets the XCTest split and the `.serialized` advice. A project can forbid any of these for its own reasons. example-app forbids `async let` because, it reports, that combination with its typed-throws client crashes at runtime.

The skills never looked for such a rule. When it wasn't already in context, they applied their own default. Claude Code's eval sandbox doesn't load a project's `CLAUDE.md`. In a scaffold whose `AGENTS.md` forbids `async let`, and where the rule names no type from the code, the plugin used `async let` in 3 of 3 runs.

## Decision

`swift:swiftui` (Operating Rules), `swift:concurrency` (a Project Rules section before Fast Path) and `swift:testing` (Agent behavior contract, item 9) carry the same sentence, byte for byte:

> Before applying this skill's defaults, read the project's own instructions (AGENTS.md, CLAUDE.md, a project skill) if they aren't already in context; when one of their rules conflicts with this skill, follow the project's rule and say which one you followed

The rule is generic; the plugin holds nothing specific to one project.
- `swift:design` and `swift:review` already defer to a project design skill through ADR-0007's rule.
- `swift:review`'s findings keep their HIG basis.

Rejected: encoding example-app's `async let` rule in the plugin. It's one project's rule, and the project already states it.

## Consequences

- Eval `project-rule-over-skill` went from 0/3 to 3/3 with the plugin. Without it, all 3 runs used `async let`, so the gain comes from the plugin.
- The sentence lives in three forked skills, so each change to it is three fork commits with Deviations rows. update-docs' cross-surface row checks that the three copies match.
