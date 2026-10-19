# ADR-0007: A project's own design layer wins over the plugin's example literals

- **Status:** accepted; amended by ADR-0011 (the rule also binds swift:review)
- **Date:** 2026-09-25
- **Source:** commits `fb7f1d7` (rule added to `swift:swiftui`), `e2b00d9` (same rule in `swift:design`), `f0ad99f` (no-layer definition and the starter-token offer), `64ee756` (template AccentColor exception); `docs/superpowers/specs/2026-09-24-swift-plugin-design.md` §1 goal 2, §4 item 6; `docs/superpowers/plans/2026-09-24-swift-plugin.md` Global Constraints (the rule word for word in both skills); `UPSTREAM.md` Deviations row "`SKILL.md` Operating Rules"

## Context

Both skills' examples use literal values: font sizes, spacing, colours, radii. `swift:design` also offers a starter token set for repos that have none. A repo with its own design layer, such as ExampleApp's planned `example-app-design`, must get every example literal translated into its tokens (spec §1, goal 2).

## Decision

Both skills carry the same operating rule: *If the project has its own design layer (tokens, a project design skill), translate every literal in these examples into it; the project layer wins on conflict.*

The Xcode template's AccentColor set alone does not make a design layer. A repo counts as having none when it has no token types, no colour sets besides that one, and no project design skill; there, `swift:design` uses system text styles and semantic colours and offers its starter tokens.

The sources record no alternative to this rule. It follows from the goal that a project layer's tokens replace the plugin's literals (spec §1, goal 2).

## Consequences

- A repo's own layer overrides both skills' literals, and a layer such as `example-app-design` can sit on top of them.
- The rule's wording is kept identical in both skills (plan, Global Constraints). An edit to one copy needs the same edit in the other, and on the `swift:swiftui` side a Deviations row.
