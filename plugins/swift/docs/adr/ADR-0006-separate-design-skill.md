# ADR-0006: Design guidance lives in a separate `swift:design` skill

- **Status:** accepted
- **Date:** 2026-09-25
- **Source:** commits `e2b00d9` (`swift:design` added), `f0ad99f` (`swift:design` tells the agent to load `swift:swiftui`); `docs/superpowers/specs/2026-09-24-swift-plugin-design.md` §2 "Improvements" and "Design guidance" rows, §5

## Context

The owner asked for a design-quality skill (spec §2, "Improvements"). It covers design judgment: which native primitive fits, when Liquid Glass fits, platform idioms, typography, colour, motion and tokens (spec §5). Upstream covers the API side of some of these topics (Dynamic Type, SF Symbols, animation) but not the design decisions. `swift:swiftui` is kept close to upstream so upstream's changes stay readable in a diff (ADR-0004).

## Decision

Put the design guidance in a new skill, `swift:design`, rather than editing it into `swift:swiftui`. `swift:design` decides what to build and where glass fits. `swift:swiftui` keeps API correctness, accessibility code patterns and Liquid Glass mechanics, and `swift:design` links to those files instead of repeating them (spec §5, "No duplication").

Rejected: scattering the design guidance through `swift:swiftui`, next to the upstream-derived content (spec §2, "Design guidance").

## Consequences

- `git diff upstream-5.1.0 -- plugins/swift/skills/swiftui` shows only the deviations `UPSTREAM.md` records, and none of them is design guidance.
- A "build a view" task can load both skills, so their SKILL.md files stay short and push detail into `references/`. `swift:design` tells the agent to load `swift:swiftui` before writing code.
