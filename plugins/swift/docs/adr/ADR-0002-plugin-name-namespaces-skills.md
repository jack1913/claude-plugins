# ADR-0002: The plugin name `swift` namespaces every skill

- **Status:** accepted
- **Date:** 2026-09-25
- **Source:** commits `e23aa05` (plugin named `swift`), `ac47417` (skill renamed to `swiftui`), `e2b00d9` (`swift:design` added); `docs/archive/specs/2026-09-24-swift-plugin-design.md` §2 "Names" row, §3 "Frontmatter" bullet, §10; `UPSTREAM.md` Deviations row "`SKILL.md` frontmatter"; spec §1 goal 2 and the ExampleApp companion spec `~/Dev/projects/example-app/docs/superpowers/specs/2026-09-24-example-app-design-layer-design.md` (depends on the skill names); `AGENTS.md` §4 "Names are fixed"

## Context

In a plugin, a skill's command is `/<plugin>:<frontmatter name>`. Upstream's skill is named `swiftui-expert-skill`, which would have made the command `/swift:swiftui-expert-skill` (spec §3). The spec picks `swift` as the plugin name because it "leaves room for non-UI skills" such as `swift:concurrency` and `swift:testing`, which it lists for later (spec §2, §10). Later non-UI skills then fit under the same plugin without a rename.

## Decision

Name the plugin `swift` and give each skill a short, unprefixed frontmatter `name`, so the commands are `swift:swiftui` and `swift:design`. Upstream's skill is renamed to `swiftui`, and the rename is logged as a deviation.

Rejected: keeping upstream's `swiftui-expert-skill` name (spec §3).

## Consequences

- A new skill takes a short `name`; the plugin supplies the `swift:` prefix.
- Renaming the plugin would rename every skill's command at once. The ExampleApp design layer depends on these names (spec §1 goal 2; ExampleApp companion spec), so they are fixed (`AGENTS.md` §4).
